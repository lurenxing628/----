from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Optional

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    is_comparison_plan,
    plan_role_label,
)

_BLOCKED_RESULT_STATUSES = frozenset(("failed", "simulated"))
_VALID_PLAN_SOURCE_TABLES = frozenset((SOURCE_SCHEDULE, SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _bool_from_summary(raw_summary: Any, key: str) -> bool:
    try:
        data = json.loads(str(raw_summary or "{}"))
    except (TypeError, ValueError):
        return False
    return bool(data.get(key)) if isinstance(data, dict) else False


def _history_is_executable(row: Dict[str, Any]) -> bool:
    result_status = _text(row.get("result_status")).lower()
    if result_status in _BLOCKED_RESULT_STATUSES:
        return False
    if _bool_from_summary(row.get("result_summary"), "is_simulation"):
        return False
    return int(row.get("schedule_row_count") or 0) > 0


def latest_executable_official_version(rows: Iterable[Dict[str, Any]]) -> Optional[int]:
    for row in rows:
        if _history_is_executable(row):
            return int(row.get("version") or 0)
    return None


def _identity_user_label(
    *,
    requested_role: str,
    status: str,
    source_table: str,
    is_scenario_preview: bool,
    scenario_display_name: str,
) -> str:
    if is_scenario_preview:
        return scenario_display_name or "模拟预览（未命名）"
    if requested_role != ROLE_ADOPTED or status in ("resolved_comparison", "fallback_to_adopted", "missing_detail"):
        return "对比参考方案"
    if source_table == SOURCE_SCHEDULE:
        return plan_role_label(ROLE_ADOPTED)
    return "对比参考方案"


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
    source = _text(source_table)
    if source not in _VALID_PLAN_SOURCE_TABLES:
        raise ValueError("计划身份缺少有效的数据来源，不能当作正式排程。")
    version_value = int(version) if version is not None else None
    latest_version = int(latest_official_version) if latest_official_version is not None else None
    is_preview = bool(scenario_id) or source == SOURCE_ADJUSTMENT_SCENARIO_ROWS or resolution_status == "scenario_preview"
    is_simulation = is_preview or _bool_from_summary(result_summary, "is_simulation")
    is_current = bool(version_value is not None and latest_version is not None and version_value == latest_version)
    is_superseded = bool(version_value is not None and latest_version is not None and version_value < latest_version)
    is_official = (
        source == SOURCE_SCHEDULE
        and requested == ROLE_ADOPTED
        and effective == ROLE_ADOPTED
        and resolution_status == "resolved_adopted"
        and not is_preview
        and not is_simulation
    )
    result_status = _text(schedule_result_status).lower() or None
    result_ok = result_status not in _BLOCKED_RESULT_STATUSES
    is_current_official = bool(is_official and is_current and result_ok)
    can_write = bool(is_current_official and not is_superseded)
    user_label = _identity_user_label(
        requested_role=requested,
        status=resolution_status,
        source_table=source,
        is_scenario_preview=is_preview,
        scenario_display_name=scenario_display_name,
    )
    label = plan_role_label(effective) if not is_preview else user_label
    if source == SOURCE_CANDIDATE_ROWS or is_comparison_plan(
        requested_role=requested,
        selected_role=effective,
        source_table=source,
        is_scenario_preview=is_preview,
    ):
        can_write = False
    if resolution_status in ("fallback_to_adopted", "missing_detail", "not_found", "historical_version"):
        can_write = False
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
        detail_saved=str(detail_saved or "").strip().lower() == "yes" or source == SOURCE_SCHEDULE,
    )
