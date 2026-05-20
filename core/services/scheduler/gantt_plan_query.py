from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

from core.infrastructure.errors import ValidationError

from .gantt_range import WeekRange, resolve_week_range
from .schedule_result_view_context import (
    attach_plan_metadata,
)
from .schedule_result_view_context import (
    default_plan_resolution_dict as _default_plan_resolution_dict,
)
from .schedule_result_view_context import (
    resolve_plan as _resolve_plan,
)
from .schedule_result_view_context import (
    selected_plan_role as _selected_plan_role,
)
from .version_resolution import VersionResolution


def default_plan_resolution_dict(plan_role: Optional[str] = None) -> Dict[str, Any]:
    try:
        return _default_plan_resolution_dict(plan_role)
    except ValidationError as exc:
        requested_role = str(plan_role or "").strip()
        if requested_role and (exc.details or {}).get("field") == "plan_role":
            raise ValidationError(f"未知的排产方案角色：{requested_role}", field="plan_role") from exc
        raise


def resolve_plan(plan_query_service, version: int, plan_role: Optional[str]):
    return _resolve_plan(plan_query_service, version, plan_role)


def selected_plan_role(plan_resolution: Dict[str, Any]) -> str:
    return _selected_plan_role(plan_resolution)


def get_version_time_span_dates(plan_query_service, version: int, plan_role: Optional[str] = None) -> Optional[Dict[str, Any]]:
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


def _has_explicit_gantt_range(
    *,
    week_start: Optional[str],
    offset_weeks: int,
    start_date: Optional[str],
    end_date: Optional[str],
) -> bool:
    try:
        offset_int = int(offset_weeks or 0)
    except Exception as e:
        raise ValidationError("周偏移填写不对，请填写整数。", field="offset_weeks") from e
    return bool(
        str(week_start or "").strip() or str(start_date or "").strip() or str(end_date or "").strip() or offset_int != 0
    )


def resolve_gantt_range_for_version(
    *,
    plan_query_service,
    version: Optional[int],
    plan_role: Optional[str] = None,
    week_start: Optional[str] = None,
    offset_weeks: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> Tuple[WeekRange, Optional[Dict[str, Any]], str]:
    version_span = (
        get_version_time_span_dates(plan_query_service, int(version), plan_role=plan_role) if version is not None else None
    )
    effective_offset_weeks = 0 if (str(start_date or "").strip() or str(end_date or "").strip()) else offset_weeks
    explicit_range = _has_explicit_gantt_range(
        week_start=week_start,
        offset_weeks=effective_offset_weeks,
        start_date=start_date,
        end_date=end_date,
    )

    if not explicit_range and version_span:
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


def _empty_message_for_out_of_range(
    *,
    tasks: Sequence[Dict[str, Any]],
    version_span: Optional[Dict[str, Any]],
    wr: WeekRange,
) -> str:
    if tasks or not version_span:
        return ""
    requested_start, requested_end = wr.week_start_date.isoformat(), wr.week_end_date.isoformat()
    actual_start, actual_end = str(version_span.get("start_date") or ""), str(version_span.get("end_date") or "")
    if requested_start == actual_start and requested_end == actual_end:
        return ""
    return f"当前范围无任务，请切换到 {actual_start} ～ {actual_end}。"


def attach_gantt_range_metadata(
    data: Dict[str, Any],
    *,
    resolution: VersionResolution,
    version_span: Optional[Dict[str, Any]],
    range_source: str,
    wr: WeekRange,
    plan_resolution: Dict[str, Any],
) -> None:
    data.update(
        has_history=True,
        status="ok",
        requested_version=resolution.requested_version,
        version_time_span=version_span,
        range_source=range_source,
    )
    attach_plan_metadata(data, plan_resolution)
    empty_message = _empty_message_for_out_of_range(tasks=list(data.get("tasks") or []), version_span=version_span, wr=wr)
    if empty_message:
        data["empty_message"] = empty_message


def build_empty_week_plan_payload(
    *,
    wr: WeekRange,
    resolution: VersionResolution,
    plan_resolution: Dict[str, Any],
) -> Dict[str, Any]:
    data = {
        "version": None,
        "requested_version": resolution.requested_version,
        "status": "no_history",
        "has_history": False,
        "week_start": wr.week_start_date.isoformat(),
        "week_end": wr.week_end_date.isoformat(),
        "rows": [],
        "degraded": False,
        "degradation_events": [],
        "degradation_counters": {},
        "empty_reason": "no_history",
        "history": None,
    }
    attach_plan_metadata(data, plan_resolution)
    return data
