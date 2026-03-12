from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from .gantt_tasks import (
    _attach_process_dependencies,
    _display_machine,
    _display_operator,
    _duration_minutes,
    _fmt_dt,
    _parse_dt,
    _priority_class,
    _sort_tasks,
)
from .gantt_week_plan import _fmt_hhmm, _split_by_day
from .resource_dispatch_range import DispatchRange


def _text(value: Any) -> str:
    return str(value or "").strip()


def _scope_type_label(scope_type: str) -> str:
    return "人员" if scope_type == "operator" else "设备"


def _counterpart_type_label(scope_type: str) -> str:
    return "设备" if scope_type == "operator" else "人员"


def _current_resource(scope_type: str, row: Dict[str, Any]) -> Dict[str, str]:
    if scope_type == "operator":
        resource_id = _text(row.get("operator_id"))
        resource_name = _text(row.get("operator_name"))
        return {
            "id": resource_id,
            "name": resource_name,
            "label": _display_operator(resource_id, resource_name),
            "team_id": _text(row.get("operator_team_id")),
            "team_name": _text(row.get("operator_team_name")),
        }

    resource_id = _text(row.get("machine_id"))
    resource_name = _text(row.get("machine_name"))
    return {
        "id": resource_id,
        "name": resource_name,
        "label": _display_machine(resource_id, resource_name, row.get("supplier_name")),
        "team_id": _text(row.get("machine_team_id")),
        "team_name": _text(row.get("machine_team_name")),
    }


def _counterpart_resource(scope_type: str, row: Dict[str, Any]) -> Dict[str, str]:
    if scope_type == "operator":
        resource_id = _text(row.get("machine_id"))
        resource_name = _text(row.get("machine_name"))
        return {
            "id": resource_id,
            "name": resource_name or _text(row.get("supplier_name")),
            "label": _display_machine(resource_id, resource_name, row.get("supplier_name")),
            "team_id": _text(row.get("machine_team_id")),
            "team_name": _text(row.get("machine_team_name")),
        }

    resource_id = _text(row.get("operator_id"))
    resource_name = _text(row.get("operator_name"))
    return {
        "id": resource_id,
        "name": resource_name,
        "label": _display_operator(resource_id, resource_name),
        "team_id": _text(row.get("operator_team_id")),
        "team_name": _text(row.get("operator_team_name")),
    }


def _team_relation_label(current_team_id: str, counterpart_team_id: str) -> str:
    if current_team_id and counterpart_team_id:
        if current_team_id == counterpart_team_id:
            return "同班组"
        return "跨班组借调"
    return "班组归属未维护"


def _clamp_to_range(st: datetime, et: datetime, dr: DispatchRange) -> Optional[Tuple[datetime, datetime]]:
    st2 = max(st, dr.start_dt)
    et2 = min(et, dr.end_dt_exclusive)
    if not (st2 < et2):
        return None
    return st2, et2


def normalize_dispatch_row(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    row: Dict[str, Any],
    overdue_set: Set[str],
) -> Optional[Dict[str, Any]]:
    st = _parse_dt(row.get("start_time"))
    et = _parse_dt(row.get("end_time"))
    if not st or not et or not (st < et):
        return None

    current = _current_resource(scope_type, row)
    counterpart = _counterpart_resource(scope_type, row)
    batch_id = _text(row.get("batch_id"))
    task_code = _text(row.get("op_code")) or (f"op_{row.get('op_id')}" if row.get("op_id") is not None else "")
    team_relation = _team_relation_label(current["team_id"], counterpart["team_id"])
    is_cross_team = bool(current["team_id"] and counterpart["team_id"] and current["team_id"] != counterpart["team_id"])
    return {
        "schedule_id": row.get("schedule_id"),
        "op_id": row.get("op_id"),
        "op_code": task_code,
        "batch_id": batch_id,
        "piece_id": _text(row.get("piece_id")),
        "part_no": _text(row.get("part_no")),
        "part_name": _text(row.get("part_name")),
        "seq": row.get("seq"),
        "op_type_name": _text(row.get("op_type_name")),
        "source": _text(row.get("source")),
        "priority": _text(row.get("priority")),
        "due_date": _text(row.get("due_date")),
        "start_time": _fmt_dt(st),
        "end_time": _fmt_dt(et),
        "duration_minutes": _duration_minutes(st, et),
        "lock_status": _text(row.get("lock_status")),
        "scope_type": scope_type,
        "scope_type_label": _scope_type_label(scope_type),
        "counterpart_type_label": _counterpart_type_label(scope_type),
        "scope_id": scope_id,
        "scope_name": scope_name,
        "scope_label": f"{scope_id} {scope_name}".strip(),
        "current_resource_id": current["id"],
        "current_resource_name": current["name"],
        "current_resource_label": current["label"],
        "current_team_id": current["team_id"],
        "current_team_name": current["team_name"],
        "counterpart_resource_id": counterpart["id"],
        "counterpart_resource_name": counterpart["name"],
        "counterpart_resource_label": counterpart["label"],
        "counterpart_team_id": counterpart["team_id"],
        "counterpart_team_name": counterpart["team_name"],
        "supplier_name": _text(row.get("supplier_name")),
        "team_relation_label": team_relation,
        "is_cross_team": is_cross_team,
        "is_cross_day": st.date() != et.date(),
        "is_overdue": bool(batch_id and batch_id in overdue_set),
    }


def build_dispatch_detail_rows(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = normalize_dispatch_row(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=scope_name,
            row=dict(row),
            overdue_set=overdue_set,
        )
        if item:
            out.append(item)
    out.sort(key=lambda item: (str(item.get("start_time") or ""), str(item.get("schedule_id") or "")))
    return out


def _normalized_row_in_range(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    dr: DispatchRange,
    row: Dict[str, Any],
    overdue_set: Set[str],
) -> Optional[Tuple[Dict[str, Any], datetime, datetime]]:
    normalized = normalize_dispatch_row(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        row=dict(row),
        overdue_set=overdue_set,
    )
    if not normalized:
        return None
    st = _parse_dt(normalized.get("start_time"))
    et = _parse_dt(normalized.get("end_time"))
    if not st or not et:
        return None
    clamped = _clamp_to_range(st, et, dr)
    if not clamped:
        return None
    return normalized, clamped[0], clamped[1]


def _task_id(normalized: Dict[str, Any]) -> str:
    if normalized.get("schedule_id") is not None:
        return f"schedule_{normalized['schedule_id']}"
    return normalized.get("op_code") or f"op_{normalized.get('op_id')}"


def _task_classes(normalized: Dict[str, Any]) -> List[str]:
    css = [_priority_class(normalized.get("priority"))]
    if normalized.get("is_overdue"):
        css.append("overdue")
    if normalized.get("is_cross_team"):
        css.append("cross-team")
    return css


def _task_group_key(normalized: Dict[str, Any], scope_id: str) -> str:
    return (
        normalized.get("current_resource_id")
        or normalized.get("current_resource_label")
        or scope_id
        or normalized.get("scope_label")
        or "resource"
    )


def _build_dispatch_task(normalized: Dict[str, Any], scope_id: str, start_dt: datetime, end_dt: datetime) -> Dict[str, Any]:
    task_id = _task_id(normalized)
    meta = dict(normalized)
    meta["group_key"] = _task_group_key(normalized, scope_id)
    meta["visible_start"] = _fmt_dt(start_dt)
    meta["visible_end"] = _fmt_dt(end_dt)
    name = f"{normalized.get('op_code') or task_id} {normalized.get('counterpart_resource_label') or ''}".strip()
    return {
        "id": task_id,
        "schedule_id": normalized.get("schedule_id"),
        "name": name,
        "start": _fmt_dt(start_dt),
        "end": _fmt_dt(end_dt),
        "duration_minutes": _duration_minutes(start_dt, end_dt),
        "progress": 0,
        "dependencies": "",
        "edge_type": "",
        "lock_status": normalized.get("lock_status"),
        "custom_class": " ".join(_task_classes(normalized)),
        "meta": meta,
    }


def build_dispatch_tasks(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> List[Dict[str, Any]]:
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        parsed = _normalized_row_in_range(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=scope_name,
            dr=dr,
            row=dict(row),
            overdue_set=overdue_set,
        )
        if not parsed:
            continue
        normalized, start_dt, end_dt = parsed
        tasks.append(_build_dispatch_task(normalized, scope_id, start_dt, end_dt))

    _attach_process_dependencies(tasks)
    _sort_tasks(tasks)
    return tasks


def _calendar_item_text(item: Dict[str, Any], start_dt: datetime, end_dt: datetime) -> str:
    parts = [f"{_fmt_hhmm(start_dt)}-{_fmt_hhmm(end_dt)}"]
    title = _text(item.get("op_code")) or _text(item.get("batch_id"))
    if title:
        parts.append(title)
    if item.get("counterpart_resource_label"):
        parts.append(_text(item.get("counterpart_resource_label")))
    if item.get("part_no"):
        parts.append(_text(item.get("part_no")))
    return " ".join(part for part in parts if part)


def _calendar_headers(dr: DispatchRange) -> List[str]:
    headers: List[str] = []
    current_day = dr.start_date
    while current_day <= dr.end_date:
        headers.append(current_day.isoformat())
        current_day = current_day.fromordinal(current_day.toordinal() + 1)
    return headers


def _calendar_group_keys(normalized: Dict[str, Any], scope_id: str) -> Tuple[str, str]:
    resource_key = _text(normalized.get("current_resource_id")) or _text(normalized.get("current_resource_label"))
    resource_label = _text(normalized.get("current_resource_label")) or _text(normalized.get("scope_label"))
    return resource_key or scope_id, resource_label


def _ensure_calendar_group(
    grouped: Dict[Tuple[str, str], Dict[str, Any]],
    *,
    headers: List[str],
    normalized: Dict[str, Any],
    scope_type: str,
    scope_id: str,
) -> Dict[str, Any]:
    resource_key, resource_label = _calendar_group_keys(normalized, scope_id)
    group_key = (resource_key, resource_label)
    group_item = grouped.get(group_key)
    if group_item is not None:
        return group_item
    group_item = {
        "scope_type": scope_type,
        "scope_type_label": _scope_type_label(scope_type),
        "scope_id": resource_key,
        "scope_name": _text(normalized.get("current_resource_name")),
        "scope_label": resource_label,
        "cells": {header: [] for header in headers},
    }
    grouped[group_key] = group_item
    return group_item


def _append_calendar_segments(group_item: Dict[str, Any], normalized: Dict[str, Any], start_dt: datetime, end_dt: datetime) -> None:
    for one_day, part_start, part_end in _split_by_day(start_dt, end_dt):
        key = one_day.isoformat()
        if key not in group_item["cells"]:
            continue
        group_item["cells"][key].append(
            {
                "start": _fmt_dt(part_start),
                "end": _fmt_dt(part_end),
                "text": _calendar_item_text(normalized, part_start, part_end),
                "batch_id": normalized.get("batch_id"),
                "op_code": normalized.get("op_code"),
                "counterpart_resource_label": normalized.get("counterpart_resource_label"),
                "is_overdue": normalized.get("is_overdue"),
            }
        )


def _calendar_cells(group_item: Dict[str, Any], headers: List[str]) -> List[Dict[str, Any]]:
    cells: List[Dict[str, Any]] = []
    for header in headers:
        items = group_item["cells"].get(header) or []
        items.sort(
            key=lambda item: (
                str(item.get("start") or ""),
                str(item.get("batch_id") or ""),
                str(item.get("op_code") or ""),
            )
        )
        cells.append({"date": header, "text": "\n".join(item.get("text") or "" for item in items), "items": items})
    return cells


def build_dispatch_calendar_matrix(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> Tuple[List[str], List[Dict[str, Any]]]:
    headers = _calendar_headers(dr)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        parsed = _normalized_row_in_range(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=scope_name,
            dr=dr,
            row=dict(row),
            overdue_set=overdue_set,
        )
        if not parsed:
            continue
        normalized, start_dt, end_dt = parsed
        group_item = _ensure_calendar_group(
            grouped,
            headers=headers,
            normalized=normalized,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        _append_calendar_segments(group_item, normalized, start_dt, end_dt)

    out_rows: List[Dict[str, Any]] = []
    for _, group_item in sorted(grouped.items(), key=lambda item: (item[0][1], item[0][0])):
        out_rows.append(
            {
                "scope_type": group_item["scope_type"],
                "scope_type_label": group_item["scope_type_label"],
                "scope_id": group_item["scope_id"],
                "scope_name": group_item["scope_name"],
                "scope_label": group_item["scope_label"],
                "cells": _calendar_cells(group_item, headers),
            }
        )

    return headers, out_rows
