"""架构扫描门面（P2 已塌缩磁盘缓存层）。

历史上本模块在 evidence/QualityGate/architecture_scan_cache.json 维护按文件
sha256 的扫描结果磁盘缓存（含 ~250 行缓存校验/合并机器）。实测全新扫描仅
~3s（577 文件），缓存带来的陈旧/投毒/校验复杂度远大于收益，P2 治理将其
塌缩为「每次直扫」：

- 公共 API（scan_files_with_cache / aggregate_architecture_scan /
  scan_single_file_architecture_fact / scan_architecture_paths_with_cache /
  architecture_scan_cache_metadata）签名与返回结构保持不变；
  cache_path / force 参数保留但不再有任何作用。
- 不再读写磁盘缓存文件；进程内复用由 quality_gate_operations 的
  _cached_architecture_aggregate 内存 memo 承担。
- architecture_scan_cache_metadata 仍被 long_gate_fingerprint 与
  run_quality_gate 回执使用，保持原字段。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, cast

from .long_gate_schema import stable_json_hash, version_hash_for_paths
from .quality_gate_ledger import entry_sort_key
from .quality_gate_scan import (
    ScanContext,
    _assign_silent_entry_ids,
    complexity_scan_map,
    scan_repository_bundle_drift_entries,
    scan_request_service_direct_assembly_entries,
    scan_silent_fallback_fact_entries,
)
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    FILE_SIZE_LIMIT,
    REPO_ROOT,
)

# 旧磁盘缓存产物路径：仅用于 clean-worktree 排除与 git hook 拦截（防止旧产物入库），不再读写。
ARCHITECTURE_SCAN_CACHE_REL = "evidence/QualityGate/architecture_scan_cache.json"
ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION = 1
ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION = 1

ARCHITECTURE_SCAN_SCANNER_VERSION_PATHS = (
    "tools/quality_gate_scan.py",
    "tools/architecture_scan_cache.py",
    "tools/quality_gate_operations.py",
    "tools/quality_gate_shared.py",
    "tools/quality_gate_ledger.py",
)
_FACT_KIND_FIELDS = {
    "silent": "silent_fallback_handlers_without_global_id",
    "complexity": "complexity_blocks_all",
    "request": "request_service_direct_assembly_entries",
    "repository": "repository_bundle_drift_entries",
}
_ALL_FACT_KINDS = tuple(_FACT_KIND_FIELDS)


def _normalize_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _radon_behavior_marker() -> str:
    try:
        version = importlib.metadata.version("radon")
    except importlib.metadata.PackageNotFoundError:
        version = ""
    except Exception:
        version = ""
    if version:
        return "version:" + version

    try:
        radon_complexity = importlib.import_module("radon.complexity")
        cc_visit = getattr(radon_complexity, "cc_visit", None)
        if not callable(cc_visit):
            raise RuntimeError("radon.complexity.cc_visit unavailable")
        rows = []
        blocks = cast(
            Sequence[Any],
            cc_visit("def sample(value):\n    if value:\n        return 1\n    return 0\n"),
        )
        for block in blocks:
            rows.append(
                {
                    "name": str(getattr(block, "name", "") or ""),
                    "complexity": int(getattr(block, "complexity", 0) or 0),
                    "lineno": int(getattr(block, "lineno", 0) or 0),
                    "letter": str(getattr(block, "letter", "") or ""),
                }
            )
        return "behavior:sha256:" + stable_json_hash(rows)
    except Exception as exc:
        payload = {"type": exc.__class__.__name__, "message": str(exc)}
        return "unavailable:sha256:" + stable_json_hash(payload)


def architecture_scan_cache_metadata(repo_root: Optional[str] = None) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or REPO_ROOT)
    return {
        "schema_version": ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION,
        "scanner_version_hash": version_hash_for_paths(root, ARCHITECTURE_SCAN_SCANNER_VERSION_PATHS),
        "scanner_schema_version": ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION,
        "python_version": sys.version.splitlines()[0].strip(),
        "radon_version_or_behavior_hash": _radon_behavior_marker(),
    }


def _normalize_fact_kinds(fact_kinds: Optional[Sequence[str]]) -> Tuple[str, ...]:
    if fact_kinds is None:
        return _ALL_FACT_KINDS
    normalized = []
    for item in list(fact_kinds or []):
        kind = str(item or "")
        if kind not in _FACT_KIND_FIELDS:
            raise ValueError(f"unknown architecture scan fact kind: {kind}")
        if kind not in normalized:
            normalized.append(kind)
    return tuple(normalized)


def scan_single_file_architecture_fact(
    rel_path: str,
    context: Optional[ScanContext] = None,
    fact_kinds: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    scan_context = context or ScanContext()
    normalized = _normalize_path(rel_path)
    kinds = _normalize_fact_kinds(fact_kinds)
    source_lines = scan_context.source_lines(normalized)
    complexity_blocks = []
    if "complexity" in kinds:
        complexity_blocks = [
            dict(item)
            for _key, item in sorted(complexity_scan_map([normalized], include_all=True, context=scan_context).items())
        ]
    return {
        "schema_version": ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION,
        "path": normalized,
        "fact_kinds": list(kinds),
        "line_count": len(source_lines),
        "silent_fallback_handlers_without_global_id": [
            dict(entry) for entry in scan_silent_fallback_fact_entries([normalized], context=scan_context)
        ] if "silent" in kinds else [],
        "complexity_blocks_all": complexity_blocks,
        "request_service_direct_assembly_entries": [
            dict(entry) for entry in scan_request_service_direct_assembly_entries([normalized], context=scan_context)
        ] if "request" in kinds else [],
        "repository_bundle_drift_entries": [
            dict(entry) for entry in scan_repository_bundle_drift_entries([normalized], context=scan_context)
        ] if "repository" in kinds else [],
    }


def scan_files_with_cache(
    paths: Sequence[str],
    cache_path: Optional[str] = None,
    force: bool = False,
    context: Optional[ScanContext] = None,
    fact_kinds: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    """对给定路径直扫并返回 facts（cache_path/force 为塌缩前遗留参数，无作用）。"""
    del cache_path, force  # 塌缩后不再有磁盘缓存
    scan_context = context or ScanContext()
    requested_kinds = _normalize_fact_kinds(fact_kinds)
    normalized_paths = sorted(set(_normalize_path(str(path)) for path in list(paths or [])))
    return [
        scan_single_file_architecture_fact(rel_path, context=scan_context, fact_kinds=requested_kinds)
        for rel_path in normalized_paths
    ]


def aggregate_architecture_scan(
    file_facts: Sequence[Mapping[str, Any]],
    mode: str = "architecture",
    include_all_complexity: bool = False,
) -> Dict[str, Any]:
    include_all = include_all_complexity or str(mode or "") == "include_all"
    silent_entries: List[Dict[str, Any]] = []
    oversize_entries: List[Dict[str, Any]] = []
    complexity_map: Dict[str, Dict[str, Any]] = {}
    request_service_entries: List[Dict[str, Any]] = []
    repository_bundle_entries: List[Dict[str, Any]] = []

    for raw_fact in sorted(list(file_facts or []), key=lambda fact: str(fact.get("path") or "")):
        fact = dict(raw_fact)
        path = _normalize_path(str(fact.get("path") or ""))
        for entry in list(fact.get("silent_fallback_handlers_without_global_id") or []):
            if isinstance(entry, dict):
                copied = dict(entry)
                copied.pop("id", None)
                silent_entries.append(copied)

        line_count = int(fact.get("line_count") or 0)
        if line_count > FILE_SIZE_LIMIT:
            oversize_entries.append({"path": path, "current_value": line_count, "limit": FILE_SIZE_LIMIT})

        for raw_block in list(fact.get("complexity_blocks_all") or []):
            if not isinstance(raw_block, dict):
                continue
            block = dict(raw_block)
            current_value = int(block.get("current_value") or 0)
            if not include_all and current_value <= COMPLEXITY_THRESHOLD:
                continue
            key = "{}:{}".format(block.get("path"), block.get("symbol"))
            complexity_map[key] = block

        for entry in list(fact.get("request_service_direct_assembly_entries") or []):
            if isinstance(entry, dict):
                request_service_entries.append(dict(entry))
        for entry in list(fact.get("repository_bundle_drift_entries") or []):
            if isinstance(entry, dict):
                repository_bundle_entries.append(dict(entry))

    _assign_silent_entry_ids(silent_entries)
    silent_entries = sorted(silent_entries, key=entry_sort_key)
    oversize_entries = sorted(oversize_entries, key=entry_sort_key)
    request_service_entries = sorted(request_service_entries, key=entry_sort_key)
    repository_bundle_entries = sorted(repository_bundle_entries, key=entry_sort_key)
    return {
        "silent_fallback_entries": silent_entries,
        "oversize_entries": oversize_entries,
        "oversize_map": {str(entry.get("path")): dict(entry) for entry in oversize_entries},
        "complexity_map": complexity_map,
        "complexity_entries": [dict(item) for _key, item in sorted(complexity_map.items())],
        "request_service_direct_assembly_entries": request_service_entries,
        "repository_bundle_drift_entries": repository_bundle_entries,
    }


def scan_architecture_paths_with_cache(
    paths: Sequence[str],
    cache_path: Optional[str] = None,
    force: bool = False,
) -> Dict[str, Any]:
    return aggregate_architecture_scan(scan_files_with_cache(paths, cache_path=cache_path, force=force))


__all__ = [
    "ARCHITECTURE_SCAN_CACHE_REL",
    "ARCHITECTURE_SCAN_CACHE_SCHEMA_VERSION",
    "ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION",
    "aggregate_architecture_scan",
    "architecture_scan_cache_metadata",
    "scan_architecture_paths_with_cache",
    "scan_files_with_cache",
    "scan_single_file_architecture_fact",
]
