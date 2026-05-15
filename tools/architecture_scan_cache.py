from __future__ import annotations

import copy
import hashlib
import importlib
import importlib.metadata
import json
import os
import sys
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
    now_shanghai_iso,
)

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


def _sha256_text(text: str) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8")).hexdigest()


def _cache_abs_path(cache_path: Optional[str]) -> str:
    rel_or_abs = str(cache_path or ARCHITECTURE_SCAN_CACHE_REL).replace("\\", "/")
    if os.path.isabs(rel_or_abs):
        return rel_or_abs
    return os.path.join(REPO_ROOT, rel_or_abs.replace("/", os.sep))


def _json_copy(value: Any) -> Any:
    return copy.deepcopy(value)


def _load_json_object(abs_path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _write_json_object(abs_path: str, payload: Mapping[str, Any]) -> None:
    parent = os.path.dirname(abs_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(abs_path, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")


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
        for block in cc_visit("def sample(value):\n    if value:\n        return 1\n    return 0\n"):
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


def _metadata_matches(payload: Mapping[str, Any], metadata: Mapping[str, Any]) -> bool:
    if not isinstance(payload.get("generated_at"), str) or not payload.get("generated_at"):
        return False
    for field in (
        "schema_version",
        "scanner_version_hash",
        "scanner_schema_version",
        "python_version",
        "radon_version_or_behavior_hash",
    ):
        if payload.get(field) != metadata.get(field):
            return False
    return isinstance(payload.get("files"), dict)


def _plain_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _has_text(entry: Mapping[str, Any], field: str) -> bool:
    return isinstance(entry.get(field), str) and bool(entry.get(field))


def _valid_silent_fact_entry(entry: Any, expected_path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("path") or "") != expected_path:
        return False
    if "id" in entry:
        return False
    for field in ("symbol", "handler_fingerprint", "handler_context_hash", "fallback_kind"):
        if not _has_text(entry, field):
            return False
    if not isinstance(entry.get("signature"), dict):
        return False
    for field in ("except_ordinal", "line_start", "line_end"):
        if not _plain_int(entry.get(field)):
            return False
    if not isinstance(entry.get("legacy_swallow_hit"), bool):
        return False
    if "scope_tag" in entry and not isinstance(entry.get("scope_tag"), str):
        return False
    return True


def _valid_complexity_fact_entry(entry: Any, expected_path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("path") or "") != expected_path:
        return False
    for field in ("symbol", "rank"):
        if not _has_text(entry, field):
            return False
    for field in ("current_value", "threshold", "line"):
        if not _plain_int(entry.get(field)):
            return False
    return True


def _valid_request_fact_entry(entry: Any, expected_path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("path") or "") != expected_path:
        return False
    if not _plain_int(entry.get("line")):
        return False
    for field in ("symbol", "rule", "target", "excerpt"):
        if not isinstance(entry.get(field), str):
            return False
    return True


def _valid_repository_fact_entry(entry: Any, expected_path: str) -> bool:
    if not isinstance(entry, dict):
        return False
    if str(entry.get("path") or "") != expected_path:
        return False
    if not _plain_int(entry.get("line")):
        return False
    for field in ("symbol", "chain", "excerpt"):
        if not isinstance(entry.get(field), str):
            return False
    if "resolved_chain" in entry and entry.get("resolved_chain") is not None and not isinstance(entry.get("resolved_chain"), str):
        return False
    return True


def _fact_is_valid(fact: Any, expected_path: str) -> bool:
    if not isinstance(fact, dict):
        return False
    if fact.get("schema_version") != ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION:
        return False
    if str(fact.get("path") or "") != expected_path:
        return False
    if not _plain_int(fact.get("line_count")):
        return False
    fact_kinds = fact.get("fact_kinds")
    if not isinstance(fact_kinds, list):
        return False
    if any(str(kind) not in _FACT_KIND_FIELDS for kind in fact_kinds):
        return False
    for field in (
        "silent_fallback_handlers_without_global_id",
        "complexity_blocks_all",
        "request_service_direct_assembly_entries",
        "repository_bundle_drift_entries",
    ):
        if not isinstance(fact.get(field), list):
            return False
    if not all(
        _valid_silent_fact_entry(entry, expected_path)
        for entry in list(fact.get("silent_fallback_handlers_without_global_id") or [])
    ):
        return False
    if not all(
        _valid_complexity_fact_entry(entry, expected_path)
        for entry in list(fact.get("complexity_blocks_all") or [])
    ):
        return False
    if not all(
        _valid_request_fact_entry(entry, expected_path)
        for entry in list(fact.get("request_service_direct_assembly_entries") or [])
    ):
        return False
    if not all(
        _valid_repository_fact_entry(entry, expected_path)
        for entry in list(fact.get("repository_bundle_drift_entries") or [])
    ):
        return False
    return True


def _cached_row_is_valid(row: Any, expected_path: str, requested_kinds: Sequence[str]) -> bool:
    if not isinstance(row, dict):
        return False
    if not isinstance(row.get("file_sha256"), str) or not row.get("file_sha256"):
        return False
    if not _fact_is_valid(row.get("fact"), expected_path):
        return False
    fact_kinds = {str(item) for item in list(row.get("fact", {}).get("fact_kinds") or [])}
    return set(requested_kinds) <= fact_kinds


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


def _merge_fact(existing: Mapping[str, Any], scanned: Mapping[str, Any]) -> Dict[str, Any]:
    merged = dict(existing)
    merged["schema_version"] = ARCHITECTURE_SCAN_FACT_SCHEMA_VERSION
    merged["path"] = str(scanned.get("path") or existing.get("path") or "")
    merged["line_count"] = int(scanned.get("line_count") or existing.get("line_count") or 0)
    merged_kinds = {str(item) for item in list(existing.get("fact_kinds") or [])}
    merged_kinds.update(str(item) for item in list(scanned.get("fact_kinds") or []))
    merged["fact_kinds"] = sorted(merged_kinds)
    for kind, field in _FACT_KIND_FIELDS.items():
        if kind in set(scanned.get("fact_kinds") or []):
            merged[field] = [dict(entry) for entry in list(scanned.get(field) or []) if isinstance(entry, dict)]
        else:
            merged.setdefault(field, [])
    return merged


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
    scan_context = context or ScanContext()
    requested_kinds = _normalize_fact_kinds(fact_kinds)
    normalized_paths = sorted(set(_normalize_path(str(path)) for path in list(paths or [])))
    metadata = architecture_scan_cache_metadata()
    abs_cache_path = _cache_abs_path(cache_path)
    payload = None if force else _load_json_object(abs_cache_path)
    cache_usable = payload is not None and _metadata_matches(payload, metadata)
    cached_files = dict(payload.get("files") or {}) if cache_usable and isinstance(payload, dict) else {}
    next_files = dict(cached_files) if cache_usable else {}
    facts: List[Dict[str, Any]] = []
    changed = force or not cache_usable

    for rel_path in normalized_paths:
        source = scan_context.read_text(rel_path)
        file_sha256 = _sha256_text(source)
        cached_row = cached_files.get(rel_path)
        if (
            not force
            and _cached_row_is_valid(cached_row, rel_path, requested_kinds)
            and str(cached_row.get("file_sha256") or "") == file_sha256
        ):
            facts.append(_json_copy(cached_row["fact"]))
            continue

        if (
            not force
            and isinstance(cached_row, dict)
            and _fact_is_valid(cached_row.get("fact"), rel_path)
            and str(cached_row.get("file_sha256") or "") == file_sha256
        ):
            cached_fact = dict(cached_row.get("fact") or {})
            cached_kinds = {str(item) for item in list(cached_fact.get("fact_kinds") or [])}
            union_kinds = sorted(cached_kinds | set(requested_kinds))
            scanned_fact = scan_single_file_architecture_fact(rel_path, context=scan_context, fact_kinds=union_kinds)
            fact = _merge_fact(cached_fact, scanned_fact)
        else:
            fact = scan_single_file_architecture_fact(rel_path, context=scan_context, fact_kinds=requested_kinds)
        next_files[rel_path] = {"file_sha256": file_sha256, "fact": _json_copy(fact)}
        facts.append(fact)
        changed = True

    if changed:
        output = dict(metadata)
        output["generated_at"] = now_shanghai_iso()
        output["files"] = next_files
        _write_json_object(abs_cache_path, output)
    return facts


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
