from __future__ import annotations

from typing import Any, Optional

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_role import COMPLETED_RESULT_STATUSES


def normalized_result_status(value: Any) -> Optional[str]:
    """Stored ScheduleHistory.result_status, trimmed and lower-cased; empty is None."""
    return str(value or "").strip().lower() or None


def build_plan_identity(
    *,
    version: int,
    source_row_id: Optional[int],
    schedule_result_status: Optional[str],
    latest_official_version: Optional[int],
) -> PlanIdentity:
    is_current_official = bool(
        version == latest_official_version
        and normalized_result_status(schedule_result_status) in COMPLETED_RESULT_STATUSES
        and source_row_id is not None
    )
    return PlanIdentity(
        version=version,
        is_current_executable_official_version=is_current_official,
        can_write_feedback=is_current_official,
    )
