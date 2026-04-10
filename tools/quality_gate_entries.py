from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Sequence, cast

from .quality_gate_shared import (
    COMPLEXITY_THRESHOLD,
    ENTRY_MANUAL_FIELDS,
    FILE_SIZE_LIMIT,
    now_shanghai_iso,
    slugify,
)


def build_default_note(source: str, fallback_kind: Optional[str] = None, scope_tag: Optional[str] = None) -> str:
    if source == "migrated_from_architecture_fitness_counter":
        return "从 tests/test_architecture_fitness.py 的旧内联事实迁移"
    if source == "baseline_scan" and scope_tag == "render_bridge":
        return "渲染桥接可观测降级，SP02 仅落账并留给 SP09 处理"
    if source == "baseline_scan" and fallback_kind:
        return "启动链基线冻结，后续治理批次再处理"
    return ""


def _default_entry_manual_fields(source: str, fallback_kind: Optional[str] = None, scope_tag: Optional[str] = None) -> Dict[str, Any]:
    owner = "SP03"
    batch = "SP03"
    if scope_tag == "render_bridge":
        owner = "SP09"
        batch = "SP09"
    return {
        "status": "open",
        "owner": owner,
        "batch": batch,
        "notes": build_default_note(source, fallback_kind=fallback_kind, scope_tag=scope_tag),
        "last_verified_at": now_shanghai_iso(),
    }


def _merge_manual_fields(existing: Optional[Dict[str, Any]], fresh: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(fresh)
    if existing is not None:
        for field_name in ENTRY_MANUAL_FIELDS:
            if field_name in existing and existing.get(field_name) not in (None, ""):
                merged[field_name] = existing.get(field_name)
        if existing.get("last_verified_at"):
            merged["last_verified_at"] = existing.get("last_verified_at")
        if existing.get("id"):
            merged["id"] = existing.get("id")
    return merged


def _maybe_refresh_last_verified(existing: Optional[Dict[str, Any]], merged: Dict[str, Any], auto_fields: Sequence[str]) -> None:
    if existing is None:
        merged["last_verified_at"] = now_shanghai_iso()
        return
    changed = False
    for field_name in auto_fields:
        if existing.get(field_name) != merged.get(field_name):
            changed = True
            break
    if not existing.get("last_verified_at"):
        changed = True
    if changed:
        merged["last_verified_at"] = now_shanghai_iso()
    else:
        merged["last_verified_at"] = existing.get("last_verified_at")


def build_oversize_entry(path: str, current_value: int, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = {
        "id": f"oversize:{slugify(path)}",
        "path": path,
        "symbol": None,
        "current_value": int(current_value),
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
        "current_value": int(current_value),
        "threshold": COMPLEXITY_THRESHOLD,
        "exit_condition": f"复杂度回落到 {COMPLEXITY_THRESHOLD} 及以下后移出白名单",
    }
    base.update(_default_entry_manual_fields(source="migrated_from_architecture_fitness_counter"))
    merged = _merge_manual_fields(existing, base)
    _maybe_refresh_last_verified(existing, merged, ["current_value", "threshold"])
    return merged


def build_silent_entry(entry: Dict[str, Any], source: str, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    scope_tag = entry.get("scope_tag")
    base = {
        "id": entry.get("id"),
        "path": entry.get("path"),
        "symbol": entry.get("symbol"),
        "handler_fingerprint": entry.get("handler_fingerprint"),
        "except_ordinal": int(entry.get("except_ordinal") or 0),
        "line_start": int(entry.get("line_start") or 0),
        "line_end": int(entry.get("line_end") or 0),
        "fallback_kind": entry.get("fallback_kind"),
        "source": source,
        "exit_condition": "去除静默吞异常，或改为可观测降级并从本分类移出",
    }
    if scope_tag is not None:
        base["scope_tag"] = scope_tag
    base.update(_default_entry_manual_fields(source=source, fallback_kind=str(entry.get("fallback_kind")), scope_tag=cast(Optional[str], scope_tag)))
    if scope_tag == "render_bridge":
        base["exit_condition"] = "完成替代渲染桥接方案或明确维持现状的长期策略"
    merged = _merge_manual_fields(existing, base)
    if source == "migrated_from_architecture_fitness_counter":
        merged["fallback_kind"] = "silent_swallow"
    _maybe_refresh_last_verified(existing, merged, ["line_start", "line_end", "handler_fingerprint", "fallback_kind", "source", "scope_tag"])
    return merged


def find_existing_by_id(entries: Sequence[Dict[str, Any]], entry_id: str) -> Optional[Dict[str, Any]]:
    for entry in entries:
        if str(entry.get("id")) == entry_id:
            return dict(entry)
    return None


def remove_entries_by_predicate(entries: Sequence[Dict[str, Any]], predicate: Callable[[Dict[str, Any]], bool]) -> List[Dict[str, Any]]:
    return [dict(entry) for entry in entries if not predicate(entry)]


__all__ = [
    "build_default_note",
    "build_complexity_entry",
    "build_oversize_entry",
    "build_silent_entry",
    "find_existing_by_id",
    "remove_entries_by_predicate",
]
