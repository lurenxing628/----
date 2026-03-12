from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence, Set

from .resource_dispatch_range import DispatchRange
from .resource_dispatch_rows import build_dispatch_calendar_matrix, build_dispatch_detail_rows, build_dispatch_tasks


def _text(value: Any) -> str:
    return str(value or "").strip()


def extract_overdue_batch_ids(result_summary: Any) -> Set[str]:
    if not result_summary:
        return set()
    try:
        payload = result_summary if isinstance(result_summary, dict) else json.loads(result_summary or "{}")
    except Exception:
        return set()
    overdue = payload.get("overdue_batches")
    if isinstance(overdue, dict):
        overdue = overdue.get("items") or []
    if not isinstance(overdue, Sequence) or isinstance(overdue, (str, bytes, bytearray)):
        return set()
    result: Set[str] = set()
    for item in overdue:
        if isinstance(item, dict):
            text = _text(item.get("batch_id") or item.get("id") or item.get("value"))
        else:
            text = _text(item)
        if text:
            result.add(text)
    return result


def filter_team_rows_by_axis(rows: Sequence[Dict[str, Any]], *, team_id: str, axis: str) -> List[Dict[str, Any]]:
    field = "operator_team_id" if axis == "operator" else "machine_team_id"
    out: List[Dict[str, Any]] = []
    for row in rows:
        if _text((row or {}).get(field)) == team_id:
            out.append(dict(row))
    return out


def build_dispatch_summary(detail_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    total_minutes = 0
    cross_day_count = 0
    overdue_count = 0
    external_count = 0
    cross_team_count = 0
    seen = set()
    for item in detail_rows:
        marker = item.get("schedule_id")
        if marker is None:
            marker = (
                item.get("op_id"),
                item.get("start_time"),
                item.get("end_time"),
                item.get("current_resource_id"),
                item.get("counterpart_resource_id"),
            )
        if marker in seen:
            continue
        seen.add(marker)
        total_minutes += int(item.get("duration_minutes") or 0)
        if item.get("is_cross_day"):
            cross_day_count += 1
        if item.get("is_overdue"):
            overdue_count += 1
        if item.get("is_cross_team"):
            cross_team_count += 1
        counterpart_id = _text(item.get("counterpart_resource_id"))
        counterpart_label = _text(item.get("counterpart_resource_label"))
        if not counterpart_id or counterpart_label.startswith("外协"):
            external_count += 1
    return {
        "total_tasks": len(seen),
        "total_hours": round(total_minutes / 60.0, 2),
        "cross_day_count": cross_day_count,
        "overdue_count": overdue_count,
        "external_count": external_count,
        "cross_team_count": cross_team_count,
    }


def count_unique_schedule_ids(rows: Sequence[Dict[str, Any]]) -> int:
    return len({row.get("schedule_id") for row in rows if row.get("schedule_id") is not None})


def build_team_cross_rows(
    *,
    team_id: str,
    team_name: str,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for row in rows:
        operator_team_id = _text((row or {}).get("operator_team_id"))
        machine_team_id = _text((row or {}).get("machine_team_id"))
        if not operator_team_id or not machine_team_id or operator_team_id == machine_team_id:
            continue
        scope_type = ""
        if operator_team_id == team_id:
            scope_type = "operator"
        elif machine_team_id == team_id:
            scope_type = "machine"
        if not scope_type:
            continue
        normalized = build_dispatch_detail_rows(
            scope_type=scope_type,
            scope_id=team_id,
            scope_name=team_name,
            rows=[row],
            overdue_set=overdue_set,
        )
        if not normalized:
            continue
        item = normalized[0]
        marker = item.get("schedule_id")
        if marker in seen:
            continue
        seen.add(marker)
        out.append(item)
    out.sort(key=lambda item: (_text(item.get("start_time")), _text(item.get("schedule_id"))))
    return out


def build_scope_result(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> Dict[str, Any]:
    detail_rows = build_dispatch_detail_rows(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        rows=rows,
        overdue_set=overdue_set,
    )
    tasks = build_dispatch_tasks(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        dr=dr,
        rows=rows,
        overdue_set=overdue_set,
    )
    calendar_headers, calendar_rows = build_dispatch_calendar_matrix(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        dr=dr,
        rows=rows,
        overdue_set=overdue_set,
    )
    return {
        "detail_rows": detail_rows,
        "tasks": tasks,
        "calendar_headers": calendar_headers,
        "calendar_rows": calendar_rows,
    }


def empty_dispatch_payload(
    *,
    scope_type: str,
    scope_type_label: str,
    team_axis: str,
    team_axis_label: str,
    version: int,
) -> Dict[str, Any]:
    return {
        "filters": {
            "scope_type": scope_type,
            "scope_type_label": scope_type_label,
            "team_axis": team_axis,
            "team_axis_label": team_axis_label,
            "version": version,
        },
        "summary": {
            "total_tasks": 0,
            "total_hours": 0,
            "cross_day_count": 0,
            "overdue_count": 0,
            "external_count": 0,
            "cross_team_count": 0,
        },
        "tasks": [],
        "detail_rows": [],
        "calendar_headers": [],
        "calendar_rows": [],
        "operator_rows": [],
        "machine_rows": [],
        "cross_team_rows": [],
        "operator_calendar_headers": [],
        "operator_calendar_rows": [],
        "machine_calendar_headers": [],
        "machine_calendar_rows": [],
        "has_history": False,
        "empty_message": "暂无排产历史，请先执行排产。",
    }


def build_team_scope_payload(
    *,
    selected_scope_id: str,
    selected_scope_name: str,
    normalized_team_axis: str,
    dr: DispatchRange,
    rows: List[Dict[str, Any]],
    overdue_set: Set[str],
) -> Dict[str, Any]:
    operator_scope = build_scope_result(
        scope_type="operator",
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=filter_team_rows_by_axis(rows, team_id=selected_scope_id, axis="operator"),
        overdue_set=overdue_set,
    )
    machine_scope = build_scope_result(
        scope_type="machine",
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=filter_team_rows_by_axis(rows, team_id=selected_scope_id, axis="machine"),
        overdue_set=overdue_set,
    )
    operator_rows = operator_scope["detail_rows"]
    machine_rows = machine_scope["detail_rows"]
    cross_team_rows = build_team_cross_rows(
        team_id=selected_scope_id,
        team_name=selected_scope_name,
        rows=rows,
        overdue_set=overdue_set,
    )
    axis_scope = machine_scope if normalized_team_axis == "machine" else operator_scope
    summary = build_dispatch_summary(list(operator_rows) + list(machine_rows))
    summary["operator_task_count"] = count_unique_schedule_ids(operator_rows)
    summary["machine_task_count"] = count_unique_schedule_ids(machine_rows)
    summary["cross_team_sheet_count"] = len(cross_team_rows)
    return {
        "summary": summary,
        "tasks": axis_scope["tasks"],
        "detail_rows": axis_scope["detail_rows"],
        "calendar_headers": axis_scope["calendar_headers"],
        "calendar_rows": axis_scope["calendar_rows"],
        "operator_rows": operator_rows,
        "machine_rows": machine_rows,
        "cross_team_rows": cross_team_rows,
        "operator_calendar_headers": operator_scope["calendar_headers"],
        "operator_calendar_rows": operator_scope["calendar_rows"],
        "machine_calendar_headers": machine_scope["calendar_headers"],
        "machine_calendar_rows": machine_scope["calendar_rows"],
    }


def build_single_scope_payload(
    *,
    normalized_scope_type: str,
    selected_scope_id: str,
    selected_scope_name: str,
    dr: DispatchRange,
    rows: List[Dict[str, Any]],
    overdue_set: Set[str],
) -> Dict[str, Any]:
    scope_result = build_scope_result(
        scope_type=normalized_scope_type,
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=rows,
        overdue_set=overdue_set,
    )
    return {
        "summary": build_dispatch_summary(scope_result["detail_rows"]),
        "tasks": scope_result["tasks"],
        "detail_rows": scope_result["detail_rows"],
        "calendar_headers": scope_result["calendar_headers"],
        "calendar_rows": scope_result["calendar_rows"],
        "operator_rows": [],
        "machine_rows": [],
        "cross_team_rows": [],
        "operator_calendar_headers": [],
        "operator_calendar_rows": [],
        "machine_calendar_headers": [],
        "machine_calendar_rows": [],
    }


def build_dispatch_filters(
    *,
    normalized_scope_type: str,
    scope_type_label: str,
    selected_scope_id: str,
    selected_scope_name: str,
    normalized_team_axis: str,
    team_axis_label: str,
    dr: DispatchRange,
    selected_version: int,
) -> Dict[str, Any]:
    return {
        "scope_type": normalized_scope_type,
        "scope_type_label": scope_type_label,
        "scope_id": selected_scope_id,
        "scope_name": selected_scope_name,
        "scope_label": f"{selected_scope_id} {selected_scope_name}".strip(),
        "operator_id": selected_scope_id if normalized_scope_type == "operator" else "",
        "machine_id": selected_scope_id if normalized_scope_type == "machine" else "",
        "team_id": selected_scope_id if normalized_scope_type == "team" else "",
        "team_axis": normalized_team_axis,
        "team_axis_label": team_axis_label,
        "period_preset": dr.period_preset,
        "period_preset_label": {
            "week": "按周",
            "month": "按月",
            "custom": "自定义",
        }.get(dr.period_preset, dr.period_preset),
        "query_date": dr.query_date.isoformat(),
        "start_date": dr.start_date.isoformat(),
        "end_date": dr.end_date.isoformat(),
        "version": selected_version,
    }


def build_empty_dispatch_message(
    *,
    normalized_scope_type: str,
    dr: DispatchRange,
    detail_rows: List[Dict[str, Any]],
    operator_rows: List[Dict[str, Any]],
    machine_rows: List[Dict[str, Any]],
) -> str:
    if normalized_scope_type == "team":
        if not operator_rows and not machine_rows:
            return f"在 {dr.start_date.isoformat()} 至 {dr.end_date.isoformat()} 范围内未查询到该班组的排班任务。"
        return ""
    if detail_rows:
        return ""
    return f"在 {dr.start_date.isoformat()} 至 {dr.end_date.isoformat()} 范围内未查询到排班任务。"
