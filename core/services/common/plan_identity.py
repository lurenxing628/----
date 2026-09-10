from __future__ import annotations

from typing import Any, Dict, Iterable, Optional, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_role import (
    COMPLETED_RESULT_STATUSES,
    ROLE_ADOPTED,
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    is_comparison_plan,
    plan_role_label,
)
from core.models.scheduler_history_parser import parse_result_summary_payload

_VALID_PLAN_SOURCE_TABLES = frozenset((SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _parsed_summary_flag_is_true(parsed: Any, key: str, *, fail_closed: bool = False) -> bool:
    # 排产摘要看不懂时必须按 fail-closed 处理；不能把解析失败当成普通 False 放行。
    if parsed.parse_failed:
        return bool(fail_closed)
    return bool((parsed.payload or {}).get(key))


def latest_official_version(rows: Iterable[Dict[str, Any]]) -> Optional[int]:
    for row in rows:
        version = int(row.get("version") or 0)
        if version > 0:
            return version
    return None


def _identity_user_label(
    *,
    requested_role: str,
    status: str,
    source_table: str,
    is_scenario_preview: bool,
    is_superseded: bool,
    scenario_display_name: str,
) -> str:
    if is_scenario_preview:
        return scenario_display_name or "模拟预览（未命名）"
    if requested_role != ROLE_ADOPTED or status in ("resolved_comparison", "fallback_to_adopted", "missing_detail"):
        return "对比参考方案"
    if is_superseded and source_table == SOURCE_SCHEDULE:
        return "历史正式方案（已被新版本替代）"
    if source_table == SOURCE_SCHEDULE:
        return plan_role_label(ROLE_ADOPTED)
    return "对比参考方案"


def _is_preview_plan(*, scenario_id: Optional[str], source_table: str, status: str) -> bool:
    return bool(scenario_id) or source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS or status == "scenario_preview"


def _is_current_version(version: Optional[int], latest_version: Optional[int]) -> bool:
    return bool(version is not None and latest_version is not None and version == latest_version)


def _is_superseded_version(version: Optional[int], latest_version: Optional[int]) -> bool:
    return bool(version is not None and latest_version is not None and version < latest_version)


def _is_official_plan(
    *,
    source_table: str,
    requested_role: str,
    effective_role: str,
    status: str,
    is_preview: bool,
    is_simulation: bool,
) -> bool:
    return (
        source_table == SOURCE_SCHEDULE
        and requested_role == ROLE_ADOPTED
        and effective_role == ROLE_ADOPTED
        and status == "resolved_adopted"
        and not is_preview
        and not is_simulation
    )


def _can_write_feedback(
    *,
    requested_role: str,
    effective_role: str,
    status: str,
    source_table: str,
    is_preview: bool,
    is_current_official: bool,
    is_superseded: bool,
) -> bool:
    if not is_current_official or is_superseded:
        return False
    if source_table == SOURCE_CANDIDATE_ROWS:
        return False
    if is_comparison_plan(
        requested_role=requested_role,
        selected_role=effective_role,
        source_table=source_table,
        is_scenario_preview=is_preview,
    ):
        return False
    return status not in ("fallback_to_adopted", "missing_detail", "not_found", "historical_version")


def _valid_source(value: Any) -> str:
    source = _text(value)
    if source not in _VALID_PLAN_SOURCE_TABLES:
        raise ValueError("计划身份缺少有效的数据来源，不能当作正式排程。")
    return source


def _int_or_none(value: Any) -> Optional[int]:
    return int(value) if value is not None else None


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


def _detail_saved(source: str, source_row_id: Optional[int], value: Any) -> bool:
    explicit_saved = str(value or "").strip().lower() == "yes"
    return bool(explicit_saved or (source == SOURCE_SCHEDULE and source_row_id is not None))


def build_plan_identity(
    *,
    version: Optional[int],
    requested_role: Optional[str],
    effective_role: str,
    status: str,
    source_table: str,
    source_row_id: Optional[int],
    candidate_id: Optional[int],
    candidate_key: Optional[str],
    scenario_id: Optional[str],
    scenario_display_name: str,
    schedule_result_status: Optional[str],
    result_summary: Optional[str],
    latest_official_version: Optional[int],
    schedule_lock_status: Optional[str],
    detail_saved: Any,
) -> PlanIdentity:
    requested = _text(requested_role) or ROLE_ADOPTED
    effective = _text(effective_role) or ROLE_ADOPTED
    resolution_status = _text(status) or "not_found"
    source = _valid_source(source_table)
    version_value = _int_or_none(version)
    latest_version = _int_or_none(latest_official_version)
    is_preview = _is_preview_plan(scenario_id=scenario_id, source_table=source, status=resolution_status)
    summary_parse = parse_result_summary_payload(result_summary)
    summary_unavailable, summary_reason = _summary_unavailable(result_summary, summary_parse)
    # is_simulation 是派工/反馈的灵魂线；摘要解析失败时按模拟方案处理，禁止写现场事实。
    is_simulation = is_preview or _parsed_summary_flag_is_true(summary_parse, "is_simulation", fail_closed=True)
    is_current = _is_current_version(version_value, latest_version)
    is_superseded = _is_superseded_version(version_value, latest_version)
    is_official = _is_official_plan(
        source_table=source,
        requested_role=requested,
        effective_role=effective,
        status=resolution_status,
        is_preview=is_preview,
        is_simulation=is_simulation,
    )
    result_status = _result_status(schedule_result_status)
    is_current_official = _is_current_official_plan(
        is_official=is_official,
        is_current=is_current,
        result_status=result_status,
        source_row_id=source_row_id,
        summary_available=not summary_unavailable,
    )
    user_label = _identity_user_label(
        requested_role=requested,
        status=resolution_status,
        source_table=source,
        is_scenario_preview=is_preview,
        is_superseded=is_superseded,
        scenario_display_name=scenario_display_name,
    )
    label = plan_role_label(effective) if not is_preview else user_label
    can_write = _can_write_feedback(
        requested_role=requested,
        effective_role=effective,
        status=resolution_status,
        source_table=source,
        is_preview=is_preview,
        is_current_official=is_current_official,
        is_superseded=is_superseded,
    )
    return PlanIdentity(
        version=version_value,
        requested_plan_role=requested,
        effective_plan_role=effective,
        plan_resolution_status=resolution_status,
        source_table=source,
        source_row_id=source_row_id,
        candidate_id=candidate_id,
        candidate_key=candidate_key,
        scenario_id=scenario_id,
        schedule_result_status=result_status,
        result_summary_parse_failed=bool(summary_unavailable),
        result_summary_parse_reason=summary_reason,
        is_simulation=bool(is_simulation),
        label=label,
        user_label=user_label,
        is_official=bool(is_official),
        is_preview=bool(is_preview),
        is_current_executable_version=bool(is_current),
        is_current_executable_official_version=bool(is_current_official),
        is_superseded_by_newer_version=bool(is_superseded),
        schedule_lock_status=schedule_lock_status,
        can_dispatch=bool(can_write),
        can_write_feedback=bool(can_write),
        detail_saved=_detail_saved(source, source_row_id, detail_saved),
    )
