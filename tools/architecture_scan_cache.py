"""架构扫描门面（P2 已塌缩磁盘缓存层）。

历史上本模块在 evidence/QualityGate/architecture_scan_cache.json 维护按文件
sha256 的扫描结果磁盘缓存（含 ~250 行缓存校验/合并机器）。实测全新扫描仅
~3s（577 文件），缓存带来的陈旧/投毒/校验复杂度远大于收益，P2 治理将其
塌缩为「每次直扫」：

- 公共 API（scan_files_with_cache / aggregate_architecture_scan /
  architecture_scan_cache_metadata）按给定路径直扫或聚合；
- 不再读写磁盘缓存文件；每次 scan_files_with_cache 新建一个扫描快照，跨次调用保持新鲜。
- 入参必须是规范的仓库相对路径（由 repo_rel 产出），本模块不改写路径身份。
- architecture_scan_cache_metadata 仍被 long_gate_fingerprint 使用，
  保存源码与实际版本或行为原文。
"""

from __future__ import annotations

import importlib
import importlib.metadata
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, cast

from .long_gate_schema import version_rows_for_paths
from .quality_gate_ledger import entry_sort_key
from .quality_gate_scan import ScanContext, complexity_scan_map, scan_silent_fallback_entries
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    FILE_SIZE_LIMIT,
    REPO_ROOT,
)

ARCHITECTURE_SCAN_SCANNER_VERSION_PATHS = (
    "tools/quality_gate_scan.py",
    "tools/architecture_scan_cache.py",
    "tools/quality_gate_operations.py",
    "tools/quality_gate_shared.py",
    "tools/quality_gate_ledger.py",
)


def _radon_behavior_marker() -> Dict[str, Any]:
    try:
        version = importlib.metadata.version("radon")
    except importlib.metadata.PackageNotFoundError:
        version = ""
    except Exception:
        version = ""
    if version:
        return {"kind": "version", "version": version}

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
        return {"kind": "behavior", "rows": rows}
    except Exception as exc:
        payload = {"type": exc.__class__.__name__, "message": str(exc)}
        return {"kind": "unavailable", "error": payload}


def architecture_scan_cache_metadata(repo_root: Optional[str] = None) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or REPO_ROOT)
    return {
        "scanner_version_content": version_rows_for_paths(root, ARCHITECTURE_SCAN_SCANNER_VERSION_PATHS),
        "python_version": sys.version.splitlines()[0].strip(),
        "radon_version_or_behavior": _radon_behavior_marker(),
    }


def scan_files_with_cache(paths: Sequence[str], fact_kinds: Sequence[str]) -> List[Dict[str, Any]]:
    """对给定路径直扫并返回 facts；同一路径可能被调用方重复传入，这里只扫一次。"""
    context = ScanContext()
    scan_silent = "silent" in fact_kinds
    scan_complexity = "complexity" in fact_kinds
    return [
        {
            "path": rel_path,
            "line_count": len(context.source_lines(rel_path)),
            "silent_fallback_entries": scan_silent_fallback_entries(rel_path, context=context) if scan_silent else [],
            "complexity_by_key": complexity_scan_map(rel_path, context=context) if scan_complexity else {},
        }
        for rel_path in sorted(set(paths))
    ]


def aggregate_architecture_scan(
    file_facts: Sequence[Mapping[str, Any]],
    *,
    include_all_complexity: bool = False,
) -> Dict[str, Any]:
    silent_entries: List[Dict[str, Any]] = []
    oversize_entries: List[Dict[str, Any]] = []
    complexity_map: Dict[str, Dict[str, Any]] = {}

    for fact in file_facts:
        path = fact["path"]
        silent_entries.extend(fact["silent_fallback_entries"])

        line_count = fact["line_count"]
        if line_count > FILE_SIZE_LIMIT:
            oversize_entries.append({"path": path, "current_value": line_count})

        # 默认只保留超阈值块；include_all 供需要区分“已退出”与“找不到”的调用方。
        complexity_map.update(
            (key, block)
            for key, block in fact["complexity_by_key"].items()
            if include_all_complexity or block["current_value"] > COMPLEXITY_THRESHOLD
        )

    silent_entries = sorted(silent_entries, key=entry_sort_key)
    return {
        "silent_fallback_entries": silent_entries,
        "oversize_entries": oversize_entries,
        "complexity_map": complexity_map,
    }


__all__ = [
    "aggregate_architecture_scan",
    "architecture_scan_cache_metadata",
    "scan_files_with_cache",
]
