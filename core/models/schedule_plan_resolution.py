from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .schedule_plan_identity import PlanIdentity
from .schedule_plan_role import plan_role_label

_IDENTITY_DEFAULTS: Dict[str, Any] = {
    "can_dispatch": False,
    "can_write_feedback": False,
    "is_official": False,
    "is_current_executable_version": False,
    "is_current_executable_official_version": False,
    "result_summary_parse_failed": False,
    "result_summary_parse_reason": "",
    "is_superseded_by_newer_version": False,
    "schedule_result_status": None,
    "schedule_lock_status": None,
    "detail_saved": False,
}


@dataclass(frozen=True)
class SchedulePlanResolution:
    version: int
    requested_role: str
    selected_role: str
    source_table: str
    status: str
    message: str
    plan_identity: Optional[PlanIdentity] = None

    def to_dict(self) -> Dict[str, Any]:
        plan_identity = self.plan_identity.to_dict() if self.plan_identity is not None else {}
        identity_fields = (
            {key: plan_identity[key] for key in _IDENTITY_DEFAULTS}
            if plan_identity
            else dict(_IDENTITY_DEFAULTS)
        )
        return {
            "version": self.version,
            "requested_role": self.requested_role,
            "requested_label": plan_role_label(self.requested_role),
            "selected_role": self.selected_role,
            "selected_label": plan_role_label(self.selected_role),
            "source_table": self.source_table,
            "status": self.status,
            "message": self.message,
            "plan_identity": plan_identity,
            "user_label": (
                (self.plan_identity.user_label if self.plan_identity is not None else "")
                or plan_role_label(self.selected_role)
            ),
            **identity_fields,
        }


__all__ = ["SchedulePlanResolution"]
