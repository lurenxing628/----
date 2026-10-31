from __future__ import annotations

from typing import Any, Optional

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_role import COMPLETED_RESULT_STATUSES
from core.models.scheduler_history_parser import ResultSummaryParseResult


def normalized_result_status(value: Any) -> Optional[str]:
    """Stored ScheduleHistory.result_status, trimmed and lower-cased; empty is None."""
    return str(value or "").strip().lower() or None


def _is_current_official_plan(
    *,
    is_official: bool,
    is_current: bool,
    result_status: Optional[str],
    source_row_id: Optional[int],
    summary_available: bool,
) -> bool:
    return bool(
        is_official
        and is_current
        and summary_available
        and result_status in COMPLETED_RESULT_STATUSES
        and source_row_id is not None
    )


def build_plan_identity(
    *,
    version: int,
    source_row_id: Optional[int],
    schedule_result_status: Optional[str],
    latest_official_version: Optional[int],
    summary_parse: ResultSummaryParseResult,
) -> PlanIdentity:
    # is_simulation 是现场反馈的灵魂线；摘要缺失或解析失败时 payload 为 None，
    # summary_available 为假，同样禁止写现场事实。
    is_simulation = bool(summary_parse.payload and summary_parse.payload.get("is_simulation"))
    is_current_official = _is_current_official_plan(
        is_official=not is_simulation,
        is_current=version == latest_official_version,
        result_status=normalized_result_status(schedule_result_status),
        source_row_id=source_row_id,
        summary_available=summary_parse.payload is not None,
    )
    return PlanIdentity(
        version=version,
        is_current_executable_official_version=is_current_official,
        can_write_feedback=is_current_official,
    )
