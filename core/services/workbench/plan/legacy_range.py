"""Parse retained Gantt bookmark ranges for workbench navigation."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.services.scheduler.schedule_result_view_range import resolve_schedule_result_week_range
from core.services.scheduler.week_range import WeekRange

LEGACY_GANTT_MAX_EXPLICIT_DATE_DAYS = 62


def resolve_legacy_gantt_range(
    *,
    plan_query_service,
    version: Optional[int],
    plan_role: Optional[str] = None,
    scenario_id: Optional[str] = None,
    week_start: Optional[str] = None,
    offset_weeks: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[WeekRange, Optional[Dict[str, Any]], str]:
    return resolve_schedule_result_week_range(
        plan_query_service=plan_query_service,
        version=version,
        plan_role=plan_role,
        scenario_id=scenario_id,
        week_start=week_start,
        offset_weeks=offset_weeks,
        start_date=start_date,
        end_date=end_date,
        default_to_version_span=True,
        max_explicit_date_days=LEGACY_GANTT_MAX_EXPLICIT_DATE_DAYS,
    )
