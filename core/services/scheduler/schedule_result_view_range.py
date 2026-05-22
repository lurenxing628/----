from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError

from .gantt_range import WeekRange, resolve_week_range


def _has_text(value: Optional[str]) -> bool:
    return bool(str(value or "").strip())


def normalize_week_offset_for_explicit_range(
    *,
    start_date: Optional[str],
    end_date: Optional[str],
    offset_weeks: Any,
) -> int:
    if _has_text(start_date) or _has_text(end_date):
        return 0
    try:
        offset_int = int(offset_weeks or 0)
    except Exception as exc:
        raise ValidationError("周偏移填写不对，请填写整数。", field="offset_weeks") from exc
    return offset_int


def has_explicit_display_range(
    *,
    week_start: Optional[str],
    offset_weeks: Any,
    start_date: Optional[str],
    end_date: Optional[str],
) -> bool:
    effective_offset = normalize_week_offset_for_explicit_range(
        start_date=start_date,
        end_date=end_date,
        offset_weeks=offset_weeks,
    )
    return bool(_has_text(week_start) or _has_text(start_date) or _has_text(end_date) or effective_offset != 0)


def get_plan_time_span_dates(
    plan_query_service,
    version: int,
    plan_role: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    try:
        span = plan_query_service.get_plan_time_span(int(version), plan_role)
    except ValueError as exc:
        raise ValidationError(str(exc), field="plan_role") from exc
    if not span:
        return None

    start_time = str(span.get("start_time") or "").strip()
    end_time = str(span.get("end_time") or "").strip()
    if not start_time or not end_time:
        return None

    start_date = start_time.replace("T", " ").split(" ", 1)[0]
    end_date = end_time.replace("T", " ").split(" ", 1)[0]
    if not start_date or not end_date:
        return None

    return {
        "version": int(version),
        "start_time": start_time,
        "end_time": end_time,
        "start_date": start_date,
        "end_date": end_date,
    }


def resolve_schedule_result_week_range(
    *,
    plan_query_service,
    version: Optional[int],
    plan_role: Optional[str] = None,
    week_start: Optional[str] = None,
    offset_weeks: Any = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    default_to_version_span: bool,
) -> Tuple[WeekRange, Optional[Dict[str, Any]], str]:
    version_span = (
        get_plan_time_span_dates(plan_query_service, int(version), plan_role=plan_role) if version is not None else None
    )
    effective_offset_weeks = normalize_week_offset_for_explicit_range(
        start_date=start_date,
        end_date=end_date,
        offset_weeks=offset_weeks,
    )
    explicit_range = has_explicit_display_range(
        week_start=week_start,
        offset_weeks=effective_offset_weeks,
        start_date=start_date,
        end_date=end_date,
    )

    if default_to_version_span and not explicit_range and version_span:
        wr = resolve_week_range(
            week_start=None,
            offset_weeks=0,
            start_date=version_span["start_date"],
            end_date=version_span["end_date"],
        )
        return wr, version_span, "version_span"

    wr = resolve_week_range(
        week_start=week_start,
        offset_weeks=effective_offset_weeks,
        start_date=start_date,
        end_date=end_date,
    )
    return wr, version_span, "request"
