"""Due-date spans for dispatch keys, plus the external candidate window.

Slack and time-left feed slack / CR / ATC, which weigh them against working-hour processing
times, so the calendar converts each wall-clock span into working hours. A calendar without
work windows (test doubles, the continuous benchmark calendar) is continuous by protocol and
keeps the wall-clock span; a batch without a due date keeps the wall-clock span to the
``datetime.max`` sentinel, where only "very far away" matters. Inside an SGS decode the span
goes through the handoff's timing memo like every other pure calendar call.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Tuple

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithm_contracts.value_domains import MERGED
from core.algorithm_runtime.piece_input import external_group_key
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_handoff
from core.shared.strict_parse import is_blank_input, parse_required_float

_NO_DUE = datetime.max


def _wall_clock_hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def working_hour_span(calendar: Any, start: datetime, end: datetime, *, priority: Any, operator_id: str) -> float:
    """Signed working hours from ``start`` to ``end`` on ``calendar``; continuous when the calendar has no windows."""
    if end == _NO_DUE or start == _NO_DUE:
        return _wall_clock_hours(start, end)
    handoff = current_sgs_handoff()
    if handoff is not None:
        calendar = handoff.timing_calendar(calendar)
    between = getattr(calendar, "working_hours_between", None)
    if between is None:
        return _wall_clock_hours(start, end)
    return float(between(start, end, priority=priority, operator_id=operator_id))


def due_span_inputs(
    calendar: Any, *, due_date: Any, est_start: datetime, est_end: datetime, priority: Any, operator_id: str,
) -> Tuple[float, float]:
    """(slack_hours, time_left_hours): working hours from the estimated end / start to the exclusive due instant."""
    due_dt = due_exclusive(due_date)
    return (
        working_hour_span(calendar, est_end, due_dt, priority=priority, operator_id=operator_id),
        working_hour_span(calendar, est_start, due_dt, priority=priority, operator_id=operator_id),
    )


def _external_candidate_window(
    ctx: Any,
    state: ScheduleRunState,
    *,
    op: Any,
    batch_id: str,
    prev_end: datetime,
    strict_mode: bool,
) -> Tuple[datetime, datetime]:
    merge_mode = str(getattr(op, "ext_merge_mode", None) or "").strip().lower()
    ext_group_id = str(getattr(op, "ext_group_id", None) or "").strip()
    if merge_mode == MERGED and ext_group_id:
        cached = state.external_group_cache.get(external_group_key(op))
        if cached:
            return cached
        total_days = _parse_external_days(
            getattr(op, "ext_group_total_days", None),
            field="ext_group_total_days",
            strict_mode=strict_mode,
        )
        return prev_end, ctx.calendar.add_calendar_days(prev_end, total_days)
    ext_days = _parse_external_days(
        getattr(op, "ext_days", None),
        field="ext_days",
        strict_mode=strict_mode,
        default_days=1.0,
    )
    return prev_end, ctx.calendar.add_calendar_days(prev_end, ext_days)


def _parse_external_days(value: Any, *, field: str, strict_mode: bool, default_days: Optional[float] = None) -> float:
    if not strict_mode and is_blank_input(value) and default_days is not None:
        return float(default_days)
    return parse_required_float(value, field=field, min_value=0.0, min_inclusive=False)


__all__ = ["due_span_inputs", "working_hour_span", "_external_candidate_window", "_parse_external_days"]
