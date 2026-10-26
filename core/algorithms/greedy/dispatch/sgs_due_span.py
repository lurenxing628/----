"""Due-date spans for dispatch keys, plus the external candidate window.

Slack and time-left feed slack / CR / ATC, which weigh them against working-hour processing
times, so the calendar converts each wall-clock span into working hours (a round-the-clock
calendar answers the wall-clock span itself). Working hours are counted only up to the run's
planning horizon; beyond it a due date is simply far away (ERP sentinels such as 2099-12-31, or
none at all) and the span continues in wall-clock hours, so the calendar never walks day by day
towards it.
Inside an SGS decode the span goes through the handoff's timing memo like every other pure
calendar call.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Mapping, Optional, Tuple

from core.algorithm_contracts.date_parsers import due_exclusive
from core.algorithm_contracts.material_release import released_start
from core.algorithm_contracts.value_domains import MERGED
from core.algorithm_runtime.piece_input import external_group_key
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_handoff

if TYPE_CHECKING:
    from core.algorithm_contracts.types import OpForScheduleAlgo

# A run without a planning end counts working hours this far past the estimated start; a due date
# beyond it only matters by its wall-clock distance, whatever the calendar says about those years.
FAR_DUE_LOOKAHEAD = timedelta(days=366)


def _wall_clock_hours(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 3600.0


def _calendar_hours(calendar: Any, start: datetime, end: datetime, *, priority: Any, operator_id: str) -> float:
    """Signed working hours on ``calendar``."""
    if start == end:
        return 0.0
    handoff = current_sgs_handoff()
    if handoff is not None:
        calendar = handoff.timing_calendar(calendar)
    return float(calendar.working_hours_between(start, end, priority=priority, operator_id=operator_id))


def working_hour_span(calendar: Any, start: datetime, end: datetime, *, priority: Any, operator_id: str,
                      horizon: datetime) -> float:
    """Signed hours from ``start`` to ``end``: working hours up to ``horizon``, wall-clock hours beyond it."""
    working = _calendar_hours(calendar, min(start, horizon), min(end, horizon), priority=priority, operator_id=operator_id)
    return working + _wall_clock_hours(max(start, horizon), max(end, horizon))


def due_span_inputs(
    calendar: Any, *, due_date: Any, est_start: datetime, est_end: datetime, priority: Any, operator_id: str,
    horizon: Optional[datetime],
) -> Tuple[float, float]:
    """(slack_hours, time_left_hours): hours from the estimated end / start to the exclusive due instant.

    ``horizon`` is the run's exclusive planning end; a run without one looks ``FAR_DUE_LOOKAHEAD`` past
    ``est_start``, so both spans share one horizon and differ by exactly the working hours of the estimate.
    """
    due_dt = due_exclusive(due_date)
    limit = horizon if horizon is not None else est_start + FAR_DUE_LOOKAHEAD
    return (
        working_hour_span(calendar, est_end, due_dt, priority=priority, operator_id=operator_id, horizon=limit),
        working_hour_span(calendar, est_start, due_dt, priority=priority, operator_id=operator_id, horizon=limit),
    )


def external_candidate_window(
    calendar: Any,
    group_cache: Mapping[Tuple[str, ...], Tuple[datetime, datetime]],
    *,
    op: OpForScheduleAlgo,
    prev_end: datetime,
) -> Tuple[datetime, datetime]:
    """The window the formal placement in external_groups.schedule_external would take, read the same way.

    Same material-release lower bound and the same already-normalized durations: a merged group
    (the input builder always names its group) spans ext_group_total_days, any other external
    operation advances by its own ext_days. ``group_cache`` holds the already placed merged-group blocks.
    """
    prev_end = released_start(op, prev_end)
    if op.ext_merge_mode == MERGED:
        cached = group_cache.get(external_group_key(op))
        if cached:
            return cached
        return prev_end, calendar.add_calendar_days(prev_end, op.ext_group_total_days)
    return prev_end, calendar.add_calendar_days(prev_end, op.ext_days)


__all__ = ["FAR_DUE_LOOKAHEAD", "due_span_inputs", "working_hour_span", "external_candidate_window"]
