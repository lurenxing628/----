from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

from core.models.schedule_plan_role import (
    COMPLETED_RESULT_STATUSES,
    ROLE_ADOPTED,
    SOURCE_SCHEDULE,
    truthy_contract_bool,
)


def can_read_execution_review(plan_resolution: Optional[Mapping[str, Any]]) -> bool:
    data: Dict[str, Any] = dict(plan_resolution or {})
    raw_identity = data.get("plan_identity")
    identity: Dict[str, Any] = dict(raw_identity) if isinstance(raw_identity, dict) else {}
    status = str(identity.get("schedule_result_status") or data.get("schedule_result_status") or "").strip().lower()
    return bool(
        data.get("source_table") == SOURCE_SCHEDULE
        and data.get("selected_role") == ROLE_ADOPTED
        and truthy_contract_bool(identity.get("is_official"))
        and not truthy_contract_bool(identity.get("is_preview"))
        and not truthy_contract_bool(identity.get("is_simulation"))
        and not truthy_contract_bool(identity.get("result_summary_parse_failed"))
        and status in COMPLETED_RESULT_STATUSES
        and truthy_contract_bool(identity.get("detail_saved"))
    )


__all__ = ["can_read_execution_review"]
