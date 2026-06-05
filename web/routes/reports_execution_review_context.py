from __future__ import annotations

from typing import Any, Dict

from core.models.schedule_plan_role import ROLE_ADOPTED, VALID_PLAN_ROLES, plan_role_label


def blocked_execution_review_plan_resolution(
    plan_resolution: Dict[str, Any],
    raw_plan_role: Any,
    scenario_id: Any,
) -> Dict[str, Any]:
    data = dict(plan_resolution or {})
    raw_role = str(raw_plan_role or ROLE_ADOPTED).strip() or ROLE_ADOPTED
    requested_role = raw_role if raw_role in VALID_PLAN_ROLES else ROLE_ADOPTED
    scenario_text = str(scenario_id or "").strip()
    scenario_label = "模拟预览身份" if scenario_text else ""
    role_label = scenario_label or plan_role_label(raw_role)
    data.update(
        {
            "requested_role": requested_role,
            "selected_role": requested_role,
            "selected_label": role_label,
            "user_label": role_label,
            "scenario_id": scenario_text or None,
            "scenario_name": scenario_label,
            "scenario_display_name": scenario_label,
            "is_scenario_preview": bool(scenario_text),
            "is_preview": bool(scenario_text),
            "is_comparison": raw_role != ROLE_ADOPTED or bool(scenario_text),
            "can_dispatch": False,
            "can_write_feedback": False,
            "is_current_executable_official_version": False,
        }
    )
    return data


def execution_review_context_overrides(identity_error: str) -> Dict[str, Any]:
    if not identity_error:
        return {}
    return {
        "plan_identity_blocking_error": True,
        "plan_identity_error": identity_error,
        "plan_identity_blocking_scope": "workbench_continuation",
        "can_dispatch": False,
        "can_write_feedback": False,
    }


__all__ = ["blocked_execution_review_plan_resolution", "execution_review_context_overrides"]
