from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Sequence, Set

from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import (
    DegradationCollector,
    degradation_events_to_dicts,
)

from ._sched_display_utils import BAD_TIME_EMPTY_REASON as _BAD_TIME_EMPTY_REASON
from .resource_dispatch_range import DispatchRange
from .resource_dispatch_rows import (
    build_dispatch_calendar_matrix,
    build_dispatch_detail_rows,
    build_dispatch_tasks,
    prepare_dispatch_rows,
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def extract_overdue_batch_ids_with_meta(result_summary: Any) -> Dict[str, Any]:
    meta: Dict[str, Any] = {
        "ids": [],
        "degraded": False,
        "partial": False,
        "message": "",
        "reason": "",
    }
    if not result_summary:
        meta["degraded"] = True
        meta["message"] = "排产摘要缺失，超期统计和标记可能不完整。"
        meta["reason"] = "result_summary_missing"
        return meta
    try:
        payload = result_summary if isinstance(result_summary, dict) else json.loads(result_summary or "{}")
    except Exception as exc:
        meta["degraded"] = True
        meta["message"] = "排产摘要解析失败，超期统计和标记可能不完整。"
        meta["reason"] = f"result_summary_json:{exc.__class__.__name__}"
        return meta
    overdue = payload.get("overdue_batches")
    if overdue is None:
        meta["degraded"] = True
        meta["message"] = "排产摘要缺少 overdue_batches，超期统计和标记可能不完整。"
        meta["reason"] = "overdue_batches_missing"
        return meta
    if isinstance(overdue, dict):
        overdue = overdue.get("items")
        if overdue is None:
            meta["degraded"] = True
            meta["message"] = "排产摘要中的 overdue_batches.items 缺失，超期统计和标记可能不完整。"
            meta["reason"] = "overdue_items_missing"
            return meta
    if not isinstance(overdue, Sequence) or isinstance(overdue, (str, bytes, bytearray)):
        meta["degraded"] = True
        meta["message"] = "排产摘要中的 overdue_batches 格式不正确，超期统计和标记可能不完整。"
        meta["reason"] = "overdue_batches_invalid_type"
        return meta
    result: List[str] = []
    seen: Set[str] = set()
    invalid_items = 0
    for item in overdue:
        if isinstance(item, dict):
            text = _text(item.get("batch_id") or item.get("id") or item.get("value"))
        else:
            text = _text(item)
        if text:
            if text not in seen:
                seen.add(text)
                result.append(text)
        else:
            invalid_items += 1
    if invalid_items > 0 and result:
        meta["partial"] = True
        meta["message"] = "排产摘要中的部分超期明细格式不正确，当前仅按已识别条目标记，结果可能仍有遗漏。"
        meta["reason"] = "overdue_item_partial"
    elif invalid_items > 0:
        meta["degraded"] = True
        meta["message"] = "排产摘要中的超期明细格式不正确，无法识别超期批次，超期统计和标记可能不完整。"
        meta["reason"] = "overdue_item_invalid"
    meta["ids"] = result
    return meta


def extract_overdue_batch_ids(result_summary: Any) -> Set[str]:
    meta = extract_overdue_batch_ids_with_meta(result_summary)
    result: Set[str] = set()
    for item in meta.get("ids") or []:
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


def build_dispatch_summary(
    detail_rows: Sequence[Dict[str, Any]],
    *,
    collector: DegradationCollector,
    empty_reason: Optional[str] = "",
) -> Dict[str, Any]:
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

    summary_empty_reason = empty_reason if not seen else None
    return {
        "total_tasks": len(seen),
        "total_hours": round(total_minutes / 60.0, 2),
        "cross_day_count": cross_day_count,
        "overdue_count": overdue_count,
        "external_count": external_count,
        "cross_team_count": cross_team_count,
        "degraded": bool(collector),
        "degradation_events": degradation_events_to_dicts(collector.to_list()),
        "degradation_counters": collector.to_counters(),
        "empty_reason": summary_empty_reason,
    }


def count_unique_schedule_ids(rows: Sequence[Dict[str, Any]]) -> int:
    return len({row.get("schedule_id") for row in rows if row.get("schedule_id") is not None})


def build_team_cross_rows(
    *,
    team_id: str,
    team_name: str,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> BuildOutcome[List[Dict[str, Any]]]:
    collector = DegradationCollector()
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
        collector.extend(normalized.events)
        if not normalized.value:
            continue
        item = normalized.value[0]
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
        out.append(item)
    out.sort(key=lambda item: (_text(item.get("start_time")), _text(item.get("schedule_id"))))
    empty_reason = None
    if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(out, collector, empty_reason=empty_reason)


def build_scope_result(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> BuildOutcome[Dict[str, Any]]:
    detail_rows_outcome = build_dispatch_detail_rows(
        scope_type=scope_type,
        scope_id=scope_id,
        scope_name=scope_name,
        rows=rows,
        overdue_set=overdue_set,
    )
    tasks_outcome = build_dispatch_tasks(
        scope_id=scope_id,
        dr=dr,
        rows=detail_rows_outcome.value,
    )
    calendar_outcome = build_dispatch_calendar_matrix(
        scope_type=scope_type,
        scope_id=scope_id,
        dr=dr,
        rows=detail_rows_outcome.value,
    )

    collector = DegradationCollector()
    collector.extend(detail_rows_outcome.events)
    collector.extend(tasks_outcome.events)
    collector.extend(calendar_outcome.events)
    empty_reason = detail_rows_outcome.empty_reason or tasks_outcome.empty_reason or calendar_outcome.empty_reason
    headers, calendar_rows = calendar_outcome.value
    return BuildOutcome.from_collector(
        {
            "detail_rows": detail_rows_outcome.value,
            "tasks": tasks_outcome.value,
            "calendar_headers": headers,
            "calendar_rows": calendar_rows,
        },
        collector,
        empty_reason=empty_reason,
    )


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
            "degraded": False,
            "degradation_events": [],
            "degradation_counters": {},
            "empty_reason": None,
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
        "overdue_markers_degraded": False,
        "overdue_markers_partial": False,
        "overdue_markers_message": "",
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
    prepared_rows = prepare_dispatch_rows(rows)
    operator_scope = build_scope_result(
        scope_type="operator",
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=filter_team_rows_by_axis(prepared_rows.value, team_id=selected_scope_id, axis="operator"),
        overdue_set=overdue_set,
    )
    machine_scope = build_scope_result(
        scope_type="machine",
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=filter_team_rows_by_axis(prepared_rows.value, team_id=selected_scope_id, axis="machine"),
        overdue_set=overdue_set,
    )
    cross_team_rows = build_team_cross_rows(
        team_id=selected_scope_id,
        team_name=selected_scope_name,
        rows=prepared_rows.value,
        overdue_set=overdue_set,
    )

    operator_payload = operator_scope.value
    machine_payload = machine_scope.value
    operator_rows = operator_payload["detail_rows"]
    machine_rows = machine_payload["detail_rows"]
    axis_scope = machine_payload if normalized_team_axis == "machine" else operator_payload

    summary_collector = DegradationCollector()
    summary_collector.extend(prepared_rows.events)
    summary_collector.extend(operator_scope.events)
    summary_collector.extend(machine_scope.events)
    summary_collector.extend(cross_team_rows.events)
    summary = build_dispatch_summary(
        list(operator_rows) + list(machine_rows),
        collector=summary_collector,
        empty_reason=(
            prepared_rows.empty_reason
            or operator_scope.empty_reason
            or machine_scope.empty_reason
            or cross_team_rows.empty_reason
        ),
    )
    summary["operator_task_count"] = count_unique_schedule_ids(operator_rows)
    summary["machine_task_count"] = count_unique_schedule_ids(machine_rows)
    summary["cross_team_sheet_count"] = len(cross_team_rows.value)
    return {
        "summary": summary,
        "tasks": axis_scope["tasks"],
        "detail_rows": axis_scope["detail_rows"],
        "calendar_headers": axis_scope["calendar_headers"],
        "calendar_rows": axis_scope["calendar_rows"],
        "operator_rows": operator_rows,
        "machine_rows": machine_rows,
        "cross_team_rows": cross_team_rows.value,
        "operator_calendar_headers": operator_payload["calendar_headers"],
        "operator_calendar_rows": operator_payload["calendar_rows"],
        "machine_calendar_headers": machine_payload["calendar_headers"],
        "machine_calendar_rows": machine_payload["calendar_rows"],
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
    prepared_rows = prepare_dispatch_rows(rows)
    scope_result = build_scope_result(
        scope_type=normalized_scope_type,
        scope_id=selected_scope_id,
        scope_name=selected_scope_name,
        dr=dr,
        rows=prepared_rows.value,
        overdue_set=overdue_set,
    )
    scope_payload = scope_result.value
    summary_collector = DegradationCollector()
    summary_collector.extend(prepared_rows.events)
    summary_collector.extend(scope_result.events)
    return {
        "summary": build_dispatch_summary(
            scope_payload["detail_rows"],
            collector=summary_collector,
            empty_reason=prepared_rows.empty_reason or scope_result.empty_reason or "",
        ),
        "tasks": scope_payload["tasks"],
        "detail_rows": scope_payload["detail_rows"],
        "calendar_headers": scope_payload["calendar_headers"],
        "calendar_rows": scope_payload["calendar_rows"],
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
    summary: Dict[str, Any],
    detail_rows: List[Dict[str, Any]],
    operator_rows: List[Dict[str, Any]],
    machine_rows: List[Dict[str, Any]],
) -> str:
    empty_reason = _text((summary or {}).get("empty_reason"))
    if empty_reason == _BAD_TIME_EMPTY_REASON:
        return f"在 {dr.start_date.isoformat()} 至 {dr.end_date.isoformat()} 范围内存在时间非法的排班数据，已全部过滤，请检查排产结果。"
    if normalized_scope_type == "team":
        if not operator_rows and not machine_rows:
            return f"在 {dr.start_date.isoformat()} 至 {dr.end_date.isoformat()} 范围内未查询到该班组的排班任务。"
        return ""
    if detail_rows:
        return ""
    return f"在 {dr.start_date.isoformat()} 至 {dr.end_date.isoformat()} 范围内未查询到排班任务。"
