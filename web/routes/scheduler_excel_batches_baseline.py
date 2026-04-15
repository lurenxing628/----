from __future__ import annotations

from typing import Any, Dict, List


def _collect_row_part_nos(rows: List[Dict[str, Any]]) -> List[str]:
    return sorted(
        {
            str((row or {}).get("图号") or "").strip()
            for row in (rows or [])
            if str((row or {}).get("图号") or "").strip()
        }
    )


def _build_parts_snapshot(parts_cache: Dict[str, Any], part_nos: List[str]) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for part_no in part_nos:
        part = parts_cache.get(part_no)
        snapshot.append(
            {
                "part_no": str(part_no),
                "part_name": getattr(part, "part_name", None),
            }
        )
    return snapshot


def _build_autobuild_parts_snapshot(parts_cache: Dict[str, Any], part_nos: List[str]) -> List[Dict[str, Any]]:
    snapshot: List[Dict[str, Any]] = []
    for part_no in part_nos:
        part = parts_cache.get(part_no)
        snapshot.append(
            {
                "part_no": str(part_no),
                "route_raw": getattr(part, "route_raw", None),
            }
        )
    return snapshot


def _build_autobuild_route_parse_snapshot(part_svc, parts_cache: Dict[str, Any], part_nos: List[str]) -> List[Dict[str, Any]]:
    if not part_nos:
        return []
    return list(
        part_svc.build_route_parse_baseline_snapshot(
            part_nos=part_nos,
            parts_cache=parts_cache,
        )
        or []
    )


def _build_template_ops_snapshot(part_operation_query_svc, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    part_nos = _collect_row_part_nos(rows)
    if not part_nos:
        return []
    return part_operation_query_svc.list_template_snapshot_for_parts(part_nos)


def _batch_baseline_extra_state(
    *,
    part_svc,
    part_operation_query_svc,
    parts_cache: Dict[str, Any],
    auto_generate_ops: bool,
    strict_mode: bool,
    rows: List[Dict[str, Any]],
) -> Dict[str, Any]:
    row_part_nos = _collect_row_part_nos(rows)
    template_ops_snapshot = _build_template_ops_snapshot(part_operation_query_svc, rows) if auto_generate_ops else []
    template_part_nos = {
        str(item.get("part_no") or "").strip()
        for item in template_ops_snapshot
        if str(item.get("part_no") or "").strip()
    }
    autobuild_part_nos = [part_no for part_no in row_part_nos if part_no not in template_part_nos] if auto_generate_ops else []
    return {
        "auto_generate_ops": bool(auto_generate_ops),
        "strict_mode": bool(strict_mode),
        "parts_snapshot": _build_parts_snapshot(parts_cache, row_part_nos),
        "template_ops_snapshot": template_ops_snapshot,
        "autobuild_parts_snapshot": _build_autobuild_parts_snapshot(parts_cache, autobuild_part_nos),
        "autobuild_route_parse_snapshot": _build_autobuild_route_parse_snapshot(part_svc, parts_cache, autobuild_part_nos),
    }


__all__ = [
    "_batch_baseline_extra_state",
    "_build_template_ops_snapshot",
]
