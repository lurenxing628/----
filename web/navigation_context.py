from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from flask import g, has_request_context, request

from core.models.schedule_plan_role import VALID_PLAN_ROLES
from web.request_resource_context import request_report_resource_context
from web.viewmodels.scheduler_navigation_links import (
    build_report_navigation_links as build_report_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    build_scheduler_navigation_links as build_scheduler_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    build_workbench_navigation_links as build_workbench_navigation_links_for_context,
)
from web.viewmodels.scheduler_navigation_links import (
    preserved_report_context_fields as preserved_report_context_fields_for_values,
)
from web.viewmodels.scheduler_workbench_links import build_workbench_plan_context

ROLE_ADOPTED = "adopted"
_NAVIGATION_CONTEXT_ATTR = "_workbench_navigation_context"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _request_arg(name: str) -> str:
    if not has_request_context():
        return ""
    return _text(request.args.get(name))


def _request_values() -> Dict[str, str]:
    if not has_request_context():
        return {}
    return {str(key): _text(request.args.get(key)) for key in request.args.keys()}


def _is_scheduler_request() -> bool:
    return has_request_context() and _text(getattr(request, "path", "")).startswith("/scheduler")


def _request_resource() -> Dict[str, str]:
    return request_report_resource_context()


def set_current_workbench_navigation_context(context: Dict[str, Any]) -> None:
    if has_request_context():
        setattr(g, _NAVIGATION_CONTEXT_ATTR, dict(context or {}))


def publish_workbench_navigation_context(**kwargs: Any) -> Dict[str, Any]:
    context = build_workbench_plan_context(**kwargs)
    set_current_workbench_navigation_context(context)
    return context


def _navigation_context_override() -> Optional[Dict[str, Any]]:
    if not has_request_context():
        return None
    context = getattr(g, _NAVIGATION_CONTEXT_ATTR, None)
    return dict(context) if isinstance(context, dict) else None


def current_workbench_navigation_context() -> Dict[str, Any]:
    override = _navigation_context_override()
    if override is not None:
        return override
    plan_role = _request_arg("plan_role")
    scenario_id = _request_arg("scenario_id")
    resource = _request_resource()
    return build_workbench_plan_context(
        version=_request_arg("version"),
        plan_role=plan_role if plan_role in VALID_PLAN_ROLES else ROLE_ADOPTED,
        scenario_id=scenario_id,
        date_from=_request_arg("start_date") or _request_arg("date_from"),
        date_to=_request_arg("end_date") or _request_arg("date_to"),
        query_date=_request_arg("query_date"),
        period_preset=_request_arg("period_preset"),
        batch_id=_request_arg("batch_id"),
        resource_type=resource["resource_type"],
        resource_id=resource["resource_id"],
        resource_label=resource["resource_label"],
        back_to=_request_arg("back_to"),
    )


def _plain_scheduler_chrome(context: Dict[str, Any]) -> bool:
    return _is_scheduler_request() and not (context.get("date_from") and context.get("date_to"))


def build_workbench_navigation_links() -> List[Dict[str, Any]]:
    context = current_workbench_navigation_context()
    return build_workbench_navigation_links_for_context(
        context,
        plain_scheduler_chrome=_plain_scheduler_chrome(context),
    )


def build_scheduler_navigation_links(active: str = "") -> List[Dict[str, Any]]:
    context = current_workbench_navigation_context()
    return build_scheduler_navigation_links_for_context(
        context,
        active=active,
        plain_scheduler_chrome=_plain_scheduler_chrome(context),
    )


def build_report_navigation_links(active: str = "") -> List[Dict[str, Any]]:
    return build_report_navigation_links_for_context(current_workbench_navigation_context(), active=active)


def preserved_report_context_fields(exclude: Iterable[str] = ()) -> List[Dict[str, str]]:
    return preserved_report_context_fields_for_values(exclude, values=_request_values())


__all__ = [
    "build_report_navigation_links",
    "build_scheduler_navigation_links",
    "build_workbench_navigation_links",
    "current_workbench_navigation_context",
    "preserved_report_context_fields",
    "publish_workbench_navigation_context",
    "set_current_workbench_navigation_context",
]
