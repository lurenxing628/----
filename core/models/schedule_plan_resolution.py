from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .schedule_plan_identity import PlanIdentity
from .schedule_plan_role import is_comparison_plan, plan_role_label, truthy_contract_bool


@dataclass(frozen=True)
class SchedulePlanRoleOption:
    role: str
    source_table: str
    candidate_id: Optional[int]
    candidate_key: Optional[str]
    candidate_label: str
    candidate_kind: Optional[str]
    candidate_status: Optional[str]
    detail_saved: Optional[str]
    selection_candidate_id: Optional[int] = None
    resolved_candidate_id: Optional[int] = None
    candidate_missing: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role,
            "label": plan_role_label(self.role),
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "selection_candidate_id": self.selection_candidate_id,
            "resolved_candidate_id": self.resolved_candidate_id,
            "candidate_key": self.candidate_key,
            "candidate_label": self.candidate_label,
            "candidate_kind": self.candidate_kind,
            "candidate_status": self.candidate_status,
            "detail_saved": self.detail_saved,
            "candidate_missing": self.candidate_missing,
            "is_comparison": is_comparison_plan(role=self.role, source_table=self.source_table),
        }


@dataclass(frozen=True)
class SchedulePlanResolution:
    version: int
    requested_role: str
    selected_role: str
    source_table: str
    candidate_id: Optional[int]
    candidate_key: Optional[str]
    status: str
    message: str
    available_roles: List[SchedulePlanRoleOption]
    scenario_id: Optional[str] = None
    scenario_name: Optional[str] = None
    is_scenario_preview: bool = False
    plan_identity: Optional[PlanIdentity] = None

    @property
    def scenario_display_name(self) -> str:
        if not truthy_contract_bool(self.is_scenario_preview):
            return ""
        return str(self.scenario_name or "").strip() or "模拟预览（未命名）"

    def to_dict(self) -> Dict[str, Any]:
        plan_identity = self.plan_identity.to_dict() if self.plan_identity is not None else {}
        return {
            "version": self.version,
            "requested_role": self.requested_role,
            "requested_label": plan_role_label(self.requested_role),
            "selected_role": self.selected_role,
            "selected_label": plan_role_label(self.selected_role),
            "source_table": self.source_table,
            "candidate_id": self.candidate_id,
            "candidate_key": self.candidate_key,
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "scenario_display_name": self.scenario_display_name,
            "status": self.status,
            "message": self.message,
            "plan_identity": plan_identity,
            "can_dispatch": truthy_contract_bool(plan_identity.get("can_dispatch")),
            "can_write_feedback": truthy_contract_bool(plan_identity.get("can_write_feedback")),
            "user_label": plan_identity.get("user_label") or self.scenario_display_name or plan_role_label(self.selected_role),
            "is_official": truthy_contract_bool(plan_identity.get("is_official")),
            "is_preview": truthy_contract_bool(plan_identity.get("is_preview")),
            "is_current_executable_version": truthy_contract_bool(plan_identity.get("is_current_executable_version")),
            "is_current_executable_official_version": truthy_contract_bool(
                plan_identity.get("is_current_executable_official_version")
            ),
            "result_summary_parse_failed": truthy_contract_bool(plan_identity.get("result_summary_parse_failed")),
            "result_summary_parse_reason": plan_identity.get("result_summary_parse_reason") or "",
            "is_superseded_by_newer_version": truthy_contract_bool(plan_identity.get("is_superseded_by_newer_version")),
            "schedule_result_status": plan_identity.get("schedule_result_status"),
            "schedule_lock_status": plan_identity.get("schedule_lock_status"),
            "detail_saved": truthy_contract_bool(plan_identity.get("detail_saved")),
            "available_roles": [item.to_dict() for item in self.available_roles],
            "is_fallback": self.status == "fallback_to_adopted",
            "is_comparison": is_comparison_plan(
                requested_role=self.requested_role,
                selected_role=self.selected_role,
                source_table=self.source_table,
                is_scenario_preview=truthy_contract_bool(self.is_scenario_preview),
            ),
            "is_scenario_preview": truthy_contract_bool(self.is_scenario_preview),
        }


__all__ = ["SchedulePlanResolution", "SchedulePlanRoleOption"]
