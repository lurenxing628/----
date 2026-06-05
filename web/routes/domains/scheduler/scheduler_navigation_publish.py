from __future__ import annotations

from typing import Any, Dict, Optional

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED
from core.services.scheduler.schedule_result_view_context import default_plan_resolution_dict, plan_role_filter_fields
from web.navigation_context import publish_workbench_navigation_context, set_current_workbench_navigation_context
from web.request_resource_context import request_report_resource_context

_GANTT_RESOURCE_VIEWS = {"machine", "operator"}
_PLAN_GUARD_FIELD_NAMES = (
    "requested_plan_role",
    "effective_plan_role",
    "plan_role_status",
    "is_scenario_preview",
    "is_comparison",
    "is_superseded_by_newer_version",
    "is_official_plan",
    "is_preview_plan",
    "is_current_executable_official_version",
    "can_dispatch",
    "can_write_feedback",
    "plan_identity_error",
    "plan_identity_blocking_error",
    "plan_identity_blocking_scope",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
)


def requested_plan_role(plan_resolution: Dict[str, Any]) -> str:
    return str(plan_resolution.get("requested_role") or ROLE_ADOPTED)


def selected_plan_role(plan_resolution: Dict[str, Any]) -> str:
    return str(plan_resolution.get("selected_role") or ROLE_ADOPTED)


def scenario_display_label(plan_resolution: Dict[str, Any]) -> str:
    return str(plan_resolution.get("scenario_display_name") or plan_resolution.get("scenario_name") or "")


def resolved_scenario_id(plan_resolution: Dict[str, Any], fallback: Optional[str] = None) -> Optional[str]:
    return plan_resolution.get("scenario_id") or fallback


def is_plan_preview(plan_resolution: Dict[str, Any]) -> bool:
    return bool(plan_resolution.get("is_scenario_preview"))


def validate_navigation_resource_aliases() -> None:
    request_report_resource_context()


def resolve_navigation_plan_context(
    services: Any,
    version: Optional[int],
    plan_role: Optional[str],
    scenario_id: Optional[str] = None,
) -> Dict[str, Any]:
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    if plan_query_service is not None and version is not None:
        try:
            return plan_query_service.resolve_plan_view(int(version), plan_role, scenario_id).to_dict()
        except ValueError as exc:
            field = "scenario_id" if scenario_id else "plan_role"
            raise ValidationError(str(exc), field=field) from exc
    gantt_service = getattr(services, "gantt_service", None)
    if gantt_service is not None and hasattr(gantt_service, "resolve_plan_context"):
        return gantt_service.resolve_plan_context(
            version,
            plan_role,
            scenario_id=scenario_id,
            plan_query_service=plan_query_service,
        )
    return default_plan_resolution_dict(plan_role)


def _plan_guard_fields(plan_resolution: Dict[str, Any]) -> Dict[str, Any]:
    fields = plan_role_filter_fields(plan_resolution)
    return {key: fields.get(key) for key in _PLAN_GUARD_FIELD_NAMES if fields.get(key) is not None}


def _publish_context(plan_resolution: Dict[str, Any], **kwargs: Any) -> Dict[str, Any]:
    guard_fields = _plan_guard_fields(plan_resolution)
    context = publish_workbench_navigation_context(
        can_write_feedback=guard_fields.get("can_write_feedback"),
        **kwargs,
    )
    context.update(guard_fields)
    set_current_workbench_navigation_context(context)
    return context


def publish_gantt_navigation_context(
    *,
    version: Any,
    plan_resolution: Dict[str, Any],
    date_from: str,
    date_to: str,
    view: str,
    gantt_resource: str,
    batch_id: Optional[str] = None,
    back_to: Optional[str] = None,
) -> Dict[str, Any]:
    validate_navigation_resource_aliases()
    resource_type = view if gantt_resource and view in _GANTT_RESOURCE_VIEWS else None
    return _publish_context(
        plan_resolution,
        version=version,
        plan_role=requested_plan_role(plan_resolution),
        scenario_id=resolved_scenario_id(plan_resolution),
        scenario_display_label=scenario_display_label(plan_resolution),
        date_from=date_from,
        date_to=date_to,
        batch_id=batch_id,
        resource_type=resource_type,
        resource_id=gantt_resource,
        resource_label=gantt_resource,
        is_preview=is_plan_preview(plan_resolution),
        back_to=back_to,
    )


def publish_analysis_navigation_context(
    *,
    version: Any,
    plan_resolution: Dict[str, Any],
    date_from: str,
    date_to: str,
    resource_context: Dict[str, Any],
    batch_id: Optional[str] = None,
    back_to: Optional[str] = None,
) -> Dict[str, Any]:
    validate_navigation_resource_aliases()
    return _publish_context(
        plan_resolution,
        version=version,
        plan_role=requested_plan_role(plan_resolution),
        scenario_id=resolved_scenario_id(plan_resolution),
        scenario_display_label=scenario_display_label(plan_resolution),
        date_from=date_from,
        date_to=date_to,
        batch_id=batch_id,
        query_date=resource_context.get("query_date"),
        period_preset=resource_context.get("period_preset"),
        resource_type=resource_context.get("resource_type"),
        resource_id=resource_context.get("resource_id"),
        is_preview=is_plan_preview(plan_resolution),
        back_to=back_to,
    )


def publish_week_plan_navigation_context(
    *,
    version: Any,
    plan_resolution: Dict[str, Any],
    fallback_scenario_id: Optional[str],
    date_from: str,
    date_to: str,
    resource_context: Optional[Dict[str, Any]] = None,
    batch_id: Optional[str] = None,
    back_to: Optional[str] = None,
) -> Dict[str, Any]:
    validate_navigation_resource_aliases()
    resource = resource_context or {}
    return _publish_context(
        plan_resolution,
        version=version,
        plan_role=requested_plan_role(plan_resolution),
        scenario_id=resolved_scenario_id(plan_resolution, fallback_scenario_id),
        scenario_display_label=scenario_display_label(plan_resolution),
        date_from=date_from,
        date_to=date_to,
        batch_id=batch_id,
        resource_type=resource.get("resource_type"),
        resource_id=resource.get("resource_id"),
        resource_label=resource.get("resource_label"),
        is_preview=is_plan_preview(plan_resolution),
        back_to=back_to,
    )
