from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence

from .long_gate_schema import content_equal
from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    ENTRY_MANUAL_FIELDS,
    FILE_SIZE_LIMIT,
    now_shanghai_iso,
    slugify,
)


def build_default_note(source: str, fallback_kind: Optional[str] = None) -> str:
    if source == "migrated_from_architecture_fitness_counter":
        return "从 tests/gate_meta/test_architecture_fitness.py 的旧内联事实迁移"
    if source == "baseline_scan" and fallback_kind:
        return "启动链基线冻结，后续治理批次再处理"
    return ""


def _default_entry_manual_fields(source: str, fallback_kind: Optional[str] = None) -> Dict[str, Any]:
    return {
        "status": "open",
        "owner": "SP03",
        "batch": "SP03",
        "notes": build_default_note(source, fallback_kind=fallback_kind),
        "last_verified_at": now_shanghai_iso(),
    }


def _merge_manual_fields(existing: Optional[Dict[str, Any]], base: Dict[str, Any]) -> Dict[str, Any]:
    if existing is not None:
        for field_name in ENTRY_MANUAL_FIELDS:
            if field_name in existing and existing.get(field_name) not in (None, ""):
                base[field_name] = existing.get(field_name)
        base["last_verified_at"] = existing["last_verified_at"]
        base["id"] = existing["id"]
    return base


def _maybe_refresh_last_verified(existing: Optional[Dict[str, Any]], merged: Dict[str, Any], auto_fields: Sequence[str]) -> None:
    if existing is None:
        merged["last_verified_at"] = now_shanghai_iso()
        return
    changed = False
    for field_name in auto_fields:
        if not content_equal(existing.get(field_name), merged.get(field_name)):
            changed = True
            break
    if changed:
        merged["last_verified_at"] = now_shanghai_iso()
    else:
        merged["last_verified_at"] = existing["last_verified_at"]


def build_oversize_entry(path: str, current_value: int, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = {
        "id": f"oversize:{slugify(path)}",
        "path": path,
        "symbol": None,
        "current_value": current_value,
        "limit": FILE_SIZE_LIMIT,
        "exit_condition": f"文件行数降到 {FILE_SIZE_LIMIT} 行及以下后移出白名单",
    }
    base.update(_default_entry_manual_fields(source="migrated_from_architecture_fitness_counter"))
    merged = _merge_manual_fields(existing, base)
    _maybe_refresh_last_verified(existing, merged, ["current_value", "limit"])
    return merged


def build_complexity_entry(path: str, symbol: str, current_value: int, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = {
        "id": f"complexity:{slugify(path)}-{slugify(symbol)}",
        "path": path,
        "symbol": symbol,
        "current_value": current_value,
        "threshold": COMPLEXITY_THRESHOLD,
        "exit_condition": f"复杂度回落到 {COMPLEXITY_THRESHOLD} 及以下后移出白名单",
    }
    base.update(_default_entry_manual_fields(source="migrated_from_architecture_fitness_counter"))
    merged = _merge_manual_fields(existing, base)
    _maybe_refresh_last_verified(existing, merged, ["current_value", "threshold"])
    return merged


def build_silent_entry(entry: Dict[str, Any], source: str, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    fallback_kind = entry["fallback_kind"]
    base: Dict[str, Any] = {
        "id": entry["id"],
        "path": entry["path"],
        "symbol": entry["symbol"],
        "except_ordinal": entry["except_ordinal"],
        "line_start": entry["line_start"],
        "line_end": entry["line_end"],
        "fallback_kind": fallback_kind,
        "source": source,
        "exit_condition": "去除静默吞异常，或改为可观测降级并从本分类移出",
        "handler_signature": entry["handler_signature"],
        "handler_context": entry["handler_context"],
    }
    if existing is not None:
        for field_name in ("handler_fingerprint", "handler_context_hash"):
            if field_name in existing:
                base[field_name] = existing[field_name]
    base.update(_default_entry_manual_fields(source=source, fallback_kind=fallback_kind))
    merged = _merge_manual_fields(existing, base)
    if existing is not None:
        for field_name in ("realigned_from", "realigned_at", "realignment_reason"):
            if existing.get(field_name) not in (None, ""):
                merged[field_name] = existing[field_name]
    _maybe_refresh_last_verified(
        existing,
        merged,
        ["line_start", "line_end", "handler_signature", "handler_context", "fallback_kind", "source"],
    )
    return merged


def remove_entries_by_predicate(entries: Sequence[Dict[str, Any]], predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
    return [entry for entry in entries if not predicate(entry)]


__all__ = [
    "build_default_note",
    "build_complexity_entry",
    "build_oversize_entry",
    "build_silent_entry",
    "remove_entries_by_predicate",
]
