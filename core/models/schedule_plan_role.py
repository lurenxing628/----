from __future__ import annotations

from typing import Any, Dict, Optional

ROLE_ADOPTED = "adopted"
ROLE_BASELINE_BEST = "baseline_best"
ROLE_CRITICAL_BEST = "critical_best"
VALID_PLAN_ROLES = (ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)

SOURCE_SCHEDULE = "schedule"
SOURCE_CANDIDATE_ROWS = "candidate_rows"
SOURCE_ADJUSTMENT_SCENARIO_ROWS = "adjustment_scenario_rows"

PLAN_ROLE_LABELS = {
    ROLE_ADOPTED: "正式采用方案",
    ROLE_BASELINE_BEST: "原算法代表方案",
    ROLE_CRITICAL_BEST: "重点工序优先代表方案",
}


def _normalize_role(role: Optional[str]) -> str:
    text = str(role or "").strip()
    return text or ROLE_ADOPTED


def is_comparison_source(source_table: Optional[str]) -> bool:
    return str(source_table or "").strip() in (SOURCE_CANDIDATE_ROWS, SOURCE_ADJUSTMENT_SCENARIO_ROWS)


def is_comparison_role(role: Optional[str]) -> bool:
    return str(role or "").strip() in (ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST)


def is_comparison_plan(
    *,
    requested_role: Optional[str] = None,
    selected_role: Optional[str] = None,
    role: Optional[str] = None,
    source_table: Optional[str] = None,
    is_scenario_preview: bool = False,
) -> bool:
    if bool(is_scenario_preview):
        return True
    return (
        is_comparison_role(requested_role or role)
        or is_comparison_role(selected_role)
        or is_comparison_source(source_table)
    )


def plan_role_label(role: Optional[str]) -> str:
    normalized = _normalize_role(role)
    return PLAN_ROLE_LABELS.get(normalized, "未知方案身份")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truthy_value(source: Dict[str, Any], keys: tuple, default: Any) -> Any:
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return default


def _truthy_override_or_data(overrides: Dict[str, Any], source: Dict[str, Any], keys: tuple, default: Any) -> Any:
    for key in keys:
        value = overrides.get(key)
        if value:
            return value
    return _truthy_value(source, keys, default)


def _override_or_data(overrides: Dict[str, Any], source: Dict[str, Any], key: str) -> Any:
    return overrides.get(key) if key in overrides else source.get(key)


def _plan_guard_status(*, requested_role: str, effective_role: str, source_table: Any) -> str:
    if effective_role == ROLE_ADOPTED and requested_role != ROLE_ADOPTED:
        return "fallback_to_adopted"
    if effective_role != ROLE_ADOPTED or is_comparison_source(source_table):
        return "resolved_comparison"
    return "resolved_adopted"


def _identity_bool(plan_identity: Dict[str, Any], source: Dict[str, Any], key: str, alias: Optional[str] = None) -> bool:
    if key in plan_identity:
        return bool(plan_identity.get(key))
    if key in source:
        return bool(source.get(key))
    if alias and alias in source:
        return bool(source.get(alias))
    return False


def _plan_guard_is_comparison(
    *,
    overrides: Dict[str, Any],
    source: Dict[str, Any],
    source_table: Any,
    requested_role: str,
    effective_role: str,
    is_scenario_preview: bool,
) -> bool:
    if is_comparison_plan(
        requested_role=requested_role,
        selected_role=effective_role,
        source_table=source_table,
        is_scenario_preview=is_scenario_preview,
    ):
        return True
    if "is_comparison" in overrides:
        return bool(overrides.get("is_comparison"))
    return bool(source.get("is_comparison"))


def project_plan_guard_fields(source: Dict[str, Any], overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    data = dict(source or {})
    override_values = dict(overrides or {})
    raw_plan_identity = data.get("plan_identity")
    plan_identity: Dict[str, Any] = dict(raw_plan_identity) if isinstance(raw_plan_identity, dict) else {}
    requested_role = str(_truthy_override_or_data(override_values, data, ("requested_role", "requested_plan_role"), ROLE_ADOPTED))
    effective_role = str(
        _truthy_override_or_data(
            override_values,
            data,
            ("effective_role", "selected_role", "effective_plan_role"),
            ROLE_ADOPTED,
        )
    )
    source_table = _override_or_data(override_values, data, "source_table")
    default_status = _plan_guard_status(
        requested_role=requested_role,
        effective_role=effective_role,
        source_table=source_table,
    )
    status = _text(_truthy_override_or_data(override_values, data, ("status", "plan_role_status"), default_status))
    message = (
        str(override_values.get("message"))
        if override_values.get("message") is not None
        else _text(data.get("message") or data.get("plan_role_message"))
    )
    is_scenario_preview = bool(_override_or_data(override_values, data, "is_scenario_preview"))
    return {
        "plan_role": requested_role,
        "requested_plan_role": requested_role,
        "effective_plan_role": effective_role,
        "plan_role_status": status,
        "plan_role_message": message,
        "plan_role_label": plan_role_label(effective_role),
        "requested_plan_role_label": plan_role_label(requested_role),
        "effective_plan_role_label": plan_role_label(effective_role),
        "candidate_id": _override_or_data(override_values, data, "candidate_id"),
        "candidate_key": _override_or_data(override_values, data, "candidate_key"),
        "source_table": source_table,
        "is_comparison": _plan_guard_is_comparison(
            overrides=override_values,
            source=data,
            source_table=source_table,
            requested_role=requested_role,
            effective_role=effective_role,
            is_scenario_preview=is_scenario_preview,
        ),
        "is_scenario_preview": is_scenario_preview,
        "scenario_id": _override_or_data(override_values, data, "scenario_id"),
        "scenario_name": _override_or_data(override_values, data, "scenario_name"),
        "scenario_display_name": _override_or_data(override_values, data, "scenario_display_name"),
        "plan_identity_label": plan_identity.get("user_label") or data.get("user_label") or plan_role_label(effective_role),
        "can_dispatch": _identity_bool(plan_identity, data, "can_dispatch"),
        "can_write_feedback": _identity_bool(plan_identity, data, "can_write_feedback"),
        "result_summary_parse_failed": bool(
            plan_identity.get("result_summary_parse_failed") or data.get("result_summary_parse_failed")
        ),
        "result_summary_parse_reason": _text(
            plan_identity.get("result_summary_parse_reason") or data.get("result_summary_parse_reason")
        ),
        "schedule_result_status": _text(
            plan_identity.get("schedule_result_status") or data.get("schedule_result_status")
        ),
        "is_official_plan": _identity_bool(plan_identity, data, "is_official", "is_official_plan"),
        "is_preview_plan": _identity_bool(plan_identity, data, "is_preview", "is_preview_plan"),
        "is_current_executable_version": _identity_bool(plan_identity, data, "is_current_executable_version"),
        "is_current_executable_official_version": _identity_bool(
            plan_identity,
            data,
            "is_current_executable_official_version",
        ),
        "is_superseded_by_newer_version": _identity_bool(plan_identity, data, "is_superseded_by_newer_version"),
    }


def plan_candidate_label(label: Optional[str], *, role: Optional[str] = None, candidate_key: Optional[str] = None) -> str:
    text = str(label or "").strip()
    key = str(candidate_key or "").strip()
    if text and text != key:
        return (
            text.replace("关键链候选", "重点工序优先方案")
            .replace("原算法候选", "原算法方案")
            .replace("重点工序优先方案最好", "重点工序优先代表方案")
            .replace("重点工序优先最好", "重点工序优先代表方案")
            .replace("关键链最好", "重点工序优先代表方案")
            .replace("原算法最好", "原算法代表方案")
            .replace("最终采用方案", "正式采用方案")
            .replace("最终采用", "正式采用方案")
        )
    if key == "baseline":
        return "原算法方案"
    if key.startswith("graph_w") and "_of_" in key:
        parts = key.replace("graph_w", "", 1).split("_of_", 1)
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return f"重点工序优先方案 {int(parts[0])}/{int(parts[1])}"
    return plan_role_label(role)


__all__ = [
    "PLAN_ROLE_LABELS",
    "ROLE_ADOPTED",
    "ROLE_BASELINE_BEST",
    "ROLE_CRITICAL_BEST",
    "SOURCE_CANDIDATE_ROWS",
    "SOURCE_ADJUSTMENT_SCENARIO_ROWS",
    "SOURCE_SCHEDULE",
    "VALID_PLAN_ROLES",
    "is_comparison_plan",
    "is_comparison_role",
    "is_comparison_source",
    "plan_candidate_label",
    "project_plan_guard_fields",
    "plan_role_label",
]
