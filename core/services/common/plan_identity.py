from __future__ import annotations

from typing import Any, Optional, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_role import (
    COMPLETED_RESULT_STATUSES,
    ROLE_ADOPTED,
    SOURCE_SCHEDULE,
    plan_role_label,
)
from core.models.scheduler_history_parser import ResultSummaryParseResult


def _text(value: Any) -> str:
    return str(value or "").strip()


def _identity_user_label(*, is_superseded: bool) -> str:
    return "历史正式方案（已被新版本替代）" if is_superseded else plan_role_label(ROLE_ADOPTED)


def _is_current_version(version: Optional[int], latest_version: Optional[int]) -> bool:
    return bool(version is not None and latest_version is not None and version == latest_version)


def _is_superseded_version(version: Optional[int], latest_version: Optional[int]) -> bool:
    return bool(version is not None and latest_version is not None and version < latest_version)


def _result_status(value: Any) -> Optional[str]:
    return _text(value).lower() or None


def _summary_unavailable(result_summary: Any, summary_parse: Any) -> Tuple[bool, str]:
    if summary_parse.parse_failed:
        return True, summary_parse.reason
    if result_summary is None or _text(result_summary) == "":
        return True, "排产摘要缺失"
    return False, ""


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


def _detail_saved(source_row_id: Optional[int]) -> bool:
    return source_row_id is not None


def build_plan_identity(
    *,
    version: Optional[int],
    source_row_id: Optional[int],
    schedule_result_status: Optional[str],
    result_summary: Optional[str],
    latest_official_version: Optional[int],
    schedule_lock_status: Optional[str],
    summary_parse: ResultSummaryParseResult,
) -> PlanIdentity:
    summary_unavailable, summary_reason = _summary_unavailable(result_summary, summary_parse)
    # is_simulation 是派工/反馈的灵魂线；摘要解析失败时按模拟方案处理，禁止写现场事实。
    is_simulation = summary_parse.parse_failed or bool(
        summary_parse.payload and summary_parse.payload.get("is_simulation")
    )
    is_current = _is_current_version(version, latest_official_version)
    is_superseded = _is_superseded_version(version, latest_official_version)
    is_official = not is_simulation
    result_status = _result_status(schedule_result_status)
    is_current_official = _is_current_official_plan(
        is_official=is_official,
        is_current=is_current,
        result_status=result_status,
        source_row_id=source_row_id,
        summary_available=not summary_unavailable,
    )
    user_label = _identity_user_label(is_superseded=is_superseded)
    label = plan_role_label(ROLE_ADOPTED)
    return PlanIdentity(
        version=version,
        requested_plan_role=ROLE_ADOPTED,
        effective_plan_role=ROLE_ADOPTED,
        plan_resolution_status="resolved_adopted",
        source_table=SOURCE_SCHEDULE,
        source_row_id=source_row_id,
        schedule_result_status=result_status,
        result_summary_parse_failed=summary_unavailable,
        result_summary_parse_reason=summary_reason,
        is_simulation=is_simulation,
        label=label,
        user_label=user_label,
        is_official=is_official,
        is_current_executable_version=is_current,
        is_current_executable_official_version=is_current_official,
        is_superseded_by_newer_version=is_superseded,
        schedule_lock_status=schedule_lock_status,
        can_dispatch=is_current_official,
        can_write_feedback=is_current_official,
        detail_saved=_detail_saved(source_row_id),
    )
