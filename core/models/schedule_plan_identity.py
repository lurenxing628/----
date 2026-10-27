from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class PlanIdentity:
    version: Optional[int]
    requested_plan_role: Optional[str]
    effective_plan_role: str
    plan_resolution_status: str
    source_table: str
    source_row_id: Optional[int]
    schedule_result_status: Optional[str]
    result_summary_parse_failed: bool
    result_summary_parse_reason: str
    is_simulation: bool
    label: str
    user_label: str
    is_official: bool
    is_current_executable_version: bool
    is_current_executable_official_version: bool
    is_superseded_by_newer_version: bool
    schedule_lock_status: Optional[str]
    can_dispatch: bool
    can_write_feedback: bool
    detail_saved: bool

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "requested_plan_role": self.requested_plan_role,
            "effective_plan_role": self.effective_plan_role,
            "plan_resolution_status": self.plan_resolution_status,
            "source_table": self.source_table,
            "source_row_id": self.source_row_id,
            "schedule_result_status": self.schedule_result_status,
            "result_summary_parse_failed": bool(self.result_summary_parse_failed),
            "result_summary_parse_reason": self.result_summary_parse_reason,
            "is_simulation": bool(self.is_simulation),
            "label": self.label,
            "user_label": self.user_label,
            "is_official": bool(self.is_official),
            "is_current_executable_version": bool(self.is_current_executable_version),
            "is_current_executable_official_version": bool(self.is_current_executable_official_version),
            "is_superseded_by_newer_version": bool(self.is_superseded_by_newer_version),
            "schedule_lock_status": self.schedule_lock_status,
            "can_dispatch": bool(self.can_dispatch),
            "can_write_feedback": bool(self.can_write_feedback),
            "detail_saved": bool(self.detail_saved),
        }


__all__ = ["PlanIdentity"]
