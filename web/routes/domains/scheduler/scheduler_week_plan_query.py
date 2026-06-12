from __future__ import annotations

from typing import Any, Dict, Optional

from flask import request, url_for

from web.request_resource_context import request_report_resource_context

from .scheduler_navigation_publish import requested_plan_role, resolved_scenario_id


def _text(value: Any) -> str:
    return str(value or "").strip()


def request_week_plan_batch_id() -> Optional[str]:
    text = _text(request.args.get("batch_id"))
    return text or None


def request_week_plan_resource_context() -> Dict[str, str]:
    return request_report_resource_context()


def _append_resource_filter(data_kwargs: Dict[str, Any], resource_context: Optional[Dict[str, Any]]) -> None:
    resource_type = _text((resource_context or {}).get("resource_type"))
    resource_id = _text((resource_context or {}).get("resource_id"))
    if resource_type or resource_id:
        data_kwargs["resource_type"] = resource_type
        data_kwargs["resource_id"] = resource_id


def week_plan_data_kwargs(
    *,
    week_start: Optional[str],
    offset_weeks: int,
    version: Any,
    plan_role: Optional[str],
    scenario_id: Optional[str],
    services: Any,
    resource_context: Optional[Dict[str, Any]] = None,
    batch_id: Optional[str] = None,
) -> Dict[str, Any]:
    data_kwargs = {
        "week_start": week_start,
        "offset_weeks": offset_weeks,
        "version": version,
    }
    if plan_role is not None:
        data_kwargs["plan_role"] = plan_role
    if scenario_id is not None:
        data_kwargs["scenario_id"] = scenario_id
    if plan_role is not None or scenario_id is not None:
        plan_query_service = getattr(services, "schedule_plan_query_service", None)
        if plan_query_service is not None:
            data_kwargs["plan_query_service"] = plan_query_service
    _append_resource_filter(data_kwargs, resource_context)
    batch_id_text = _text(batch_id)
    if batch_id_text:
        data_kwargs["batch_id"] = batch_id_text
    return data_kwargs


def _week_plan_action_url(
    endpoint: str,
    *,
    version: Any,
    week_start: str,
    plan_resolution: Dict[str, Any],
    resource_context: Optional[Dict[str, Any]] = None,
    batch_id: Optional[str] = None,
) -> Optional[str]:
    if version is None:
        return None
    args: Dict[str, Any] = {
        "week_start": week_start,
        "version": version,
        "plan_role": requested_plan_role(plan_resolution),
        "scenario_id": resolved_scenario_id(plan_resolution),
        "batch_id": batch_id,
        "resource_type": (resource_context or {}).get("resource_type"),
        "resource_id": (resource_context or {}).get("resource_id"),
    }
    return url_for(endpoint, **{key: value for key, value in args.items() if _text(value)})


def week_plan_export_url(**kwargs: Any) -> Optional[str]:
    return _week_plan_action_url("scheduler.week_plan_export", **kwargs)


def week_plan_print_url(**kwargs: Any) -> Optional[str]:
    # 打印周派工单入口（fusion-dispatch-print-sheet）：与导出同形——透传当前
    # 版本/方案身份/批次/资源筛选，打印的是当前筛选结果
    return _week_plan_action_url("scheduler.week_plan_print_page", **kwargs)


__all__ = [
    "request_week_plan_batch_id",
    "request_week_plan_resource_context",
    "week_plan_data_kwargs",
    "week_plan_export_url",
    "week_plan_print_url",
]
