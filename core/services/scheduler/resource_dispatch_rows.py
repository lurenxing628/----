from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from core.services.common.build_outcome import BuildOutcome
from core.services.common.degradation import DegradationCollector

from ._sched_display_utils import (
    BAD_TIME_EMPTY_REASON as _BAD_TIME_EMPTY_REASON,
)
from ._sched_display_utils import (
    display_machine as _display_machine,
)
from ._sched_display_utils import (
    display_operator as _display_operator,
)
from ._sched_display_utils import (
    duration_minutes as _duration_minutes,
)
from ._sched_display_utils import (
    fmt_dt as _fmt_dt,
)
from ._sched_display_utils import (
    fmt_hhmm as _fmt_hhmm,
)
from ._sched_display_utils import (
    parse_dt as _parse_dt,
)
from ._sched_display_utils import (
    priority_class as _priority_class,
)
from ._sched_display_utils import (
    record_bad_time_row as _record_bad_time_row,
)
from ._sched_display_utils import (
    split_by_day as _split_by_day,
)
from .gantt_tasks import _attach_process_dependencies, _sort_tasks
from .resource_dispatch_range import DispatchRange

_BAD_TIME_ROW_MESSAGE = "存在开始/结束时间不合法的排班行，已跳过。"


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


def _prepared_time_range(row: Dict[str, Any]) -> Tuple[Optional[datetime], Optional[datetime]]:
    start_time = row.get("_parsed_start_time")
    end_time = row.get("_parsed_end_time")
    if isinstance(start_time, datetime) and isinstance(end_time, datetime):
        return start_time, end_time
    return _parse_dt(row.get("start_time")), _parse_dt(row.get("end_time"))


def prepare_dispatch_rows(
    rows: Sequence[Dict[str, Any]],
    *,
    scope: str = "resource_dispatch.rows",
) -> BuildOutcome[List[Dict[str, Any]]]:
    collector = DegradationCollector()
    prepared_rows: List[Dict[str, Any]] = []
    for row in rows:
        current = dict(row)
        st = _parse_dt(current.get("start_time"))
        et = _parse_dt(current.get("end_time"))
        if not st or not et or not (st < et):
            _record_bad_time_row(
                collector,
                scope=scope,
                row=current,
                message=_BAD_TIME_ROW_MESSAGE,
            )
            continue
        current["_parsed_start_time"] = st
        current["_parsed_end_time"] = et
        prepared_rows.append(current)

    empty_reason = None
    if not prepared_rows and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(prepared_rows, collector, empty_reason=empty_reason)


def normalize_dispatch_row(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    row: Dict[str, Any],
    overdue_set: Set[str],
) -> BuildOutcome[Optional[Dict[str, Any]]]:
    collector = DegradationCollector()
    st, et = _prepared_time_range(row)
    if not st or not et or not (st < et):
        _record_bad_time_row(
            collector,
            scope="resource_dispatch.detail_rows",
            row=row,
            message=_BAD_TIME_ROW_MESSAGE,
        )
        return BuildOutcome.from_collector(None, collector)

    current = _current_resource(scope_type, row)
    counterpart = _counterpart_resource(scope_type, row)
    batch_id = _text(row.get("batch_id"))
    task_code = _text(row.get("op_code")) or (f"op_{row.get('op_id')}" if row.get("op_id") is not None else "")
    team_relation = _team_relation_label(current["team_id"], counterpart["team_id"])
    is_cross_team = bool(current["team_id"] and counterpart["team_id"] and current["team_id"] != counterpart["team_id"])
    normalized = {
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
        "machine_id": _text(row.get("machine_id")),
        "machine_name": _text(row.get("machine_name")),
        "machine_team_id": _text(row.get("machine_team_id")),
        "machine_team_name": _text(row.get("machine_team_name")),
        "operator_id": _text(row.get("operator_id")),
        "operator_name": _text(row.get("operator_name")),
        "operator_team_id": _text(row.get("operator_team_id")),
        "operator_team_name": _text(row.get("operator_team_name")),
        "supplier_name": _text(row.get("supplier_name")),
        "team_relation_label": team_relation,
        "is_cross_team": is_cross_team,
        "is_cross_day": st.date() != et.date(),
        "is_overdue": bool(batch_id and batch_id in overdue_set),
    }
    return BuildOutcome.from_collector(normalized, collector)


def build_dispatch_detail_rows(
    *,
    scope_type: str,
    scope_id: str,
    scope_name: str,
    rows: Sequence[Dict[str, Any]],
    overdue_set: Set[str],
) -> BuildOutcome[List[Dict[str, Any]]]:
    collector = DegradationCollector()
    out: List[Dict[str, Any]] = []
    for row in rows:
        item = normalize_dispatch_row(
            scope_type=scope_type,
            scope_id=scope_id,
            scope_name=scope_name,
            row=dict(row),
            overdue_set=overdue_set,
        )
        collector.extend(item.events)
        if item.value is not None:
            out.append(item.value)
    out.sort(key=lambda item: (str(item.get("start_time") or ""), str(item.get("schedule_id") or "")))
    empty_reason = None
    if not out and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(out, collector, empty_reason=empty_reason)


def _normalized_row_in_range(
    *,
    dr: DispatchRange,
    row: Dict[str, Any],
) -> BuildOutcome[Optional[Tuple[Dict[str, Any], datetime, datetime]]]:
    collector = DegradationCollector()
    st = _parse_dt(row.get("start_time"))
    et = _parse_dt(row.get("end_time"))
    if not st or not et or not (st < et):
        _record_bad_time_row(
            collector,
            scope="resource_dispatch.range",
            row=row,
            message=_BAD_TIME_ROW_MESSAGE,
        )
        return BuildOutcome.from_collector(None, collector)
    clamped = _clamp_to_range(st, et, dr)
    if not clamped:
        return BuildOutcome.from_collector(None, collector)
    return BuildOutcome.from_collector((row, clamped[0], clamped[1]), collector)


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
    scope_id: str,
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
) -> BuildOutcome[List[Dict[str, Any]]]:
    collector = DegradationCollector()
    tasks: List[Dict[str, Any]] = []
    for row in rows:
        parsed = _normalized_row_in_range(dr=dr, row=dict(row))
        collector.extend(parsed.events)
        if parsed.value is None:
            continue
        normalized, start_dt, end_dt = parsed.value
        tasks.append(_build_dispatch_task(normalized, scope_id, start_dt, end_dt))

    _attach_process_dependencies(tasks)
    _sort_tasks(tasks)
    empty_reason = None
    if not tasks and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector(tasks, collector, empty_reason=empty_reason)


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
    dr: DispatchRange,
    rows: Sequence[Dict[str, Any]],
) -> BuildOutcome[Tuple[List[str], List[Dict[str, Any]]]]:
    collector = DegradationCollector()
    headers = _calendar_headers(dr)
    grouped: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for row in rows:
        parsed = _normalized_row_in_range(dr=dr, row=dict(row))
        collector.extend(parsed.events)
        if parsed.value is None:
            continue
        normalized, start_dt, end_dt = parsed.value
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

    empty_reason = None
    if not out_rows and collector.to_counters().get("bad_time_row_skipped", 0) > 0:
        empty_reason = _BAD_TIME_EMPTY_REASON
    return BuildOutcome.from_collector((headers, out_rows), collector, empty_reason=empty_reason)
