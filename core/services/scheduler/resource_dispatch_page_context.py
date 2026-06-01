from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .resource_dispatch_support import build_dispatch_filters
from .schedule_plan_query_service import ROLE_ADOPTED
from .schedule_result_view_context import (
    plan_role_filter_fields,
    serialize_plan_role_options,
)


def latest_page_version(history_service: Any, versions: List[Dict[str, Any]]) -> int:
    if versions:
        return int(versions[0].get("version") or 0)
    return int(history_service.get_latest_version() or 0)


def plan_role_context_for_page(
    *,
    view_context: Any,
    selected_version: Any,
    normalized_plan_role: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    if selected_version:
        return plan_role_filter_fields(view_context), serialize_plan_role_options(view_context.available_roles)
    return (
        plan_role_filter_fields(
            requested_role=normalized_plan_role,
            effective_role=ROLE_ADOPTED,
        ),
        serialize_plan_role_options([]),
    )


def build_page_filters(
    *,
    text_value: Any,
    normalized_scope_type: str,
    normalized_team_axis: str,
    selected_scope_id: Optional[str],
    selected_scope_name: str,
    operator_id: Any,
    machine_id: Any,
    team_id: Any,
    dr: Any,
    selected_version: Any,
    batch_id: Any,
    plan_role_fields: Dict[str, Any],
) -> Dict[str, Any]:
    filters = build_dispatch_filters(
        normalized_scope_type=normalized_scope_type,
        selected_scope_id=selected_scope_id or "",
        selected_scope_name=selected_scope_name,
        normalized_team_axis=normalized_team_axis,
        dr=dr,
        selected_version=selected_version,
        batch_id=batch_id,
    )
    if normalized_scope_type != "operator":
        filters["operator_id"] = text_value(operator_id) or ""
    if normalized_scope_type != "machine":
        filters["machine_id"] = text_value(machine_id) or ""
    if normalized_scope_type != "team":
        filters["team_id"] = text_value(team_id) or ""
    filters.update(plan_role_fields)
    return filters


def can_query_page(*, selected_version: Any, scope_type: str, scope_id: Optional[str]) -> bool:
    return bool(selected_version) and (scope_type != "team" or bool(scope_id))


__all__ = [
    "build_page_filters",
    "can_query_page",
    "latest_page_version",
    "plan_role_context_for_page",
]
