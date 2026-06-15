from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import current_app

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_result_view_range import get_plan_time_span_dates
from web.viewmodels.scheduler_workbench_links import (
    FULL_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_plan_context,
)

from .scheduler_plan_context_token import plan_context_token


def _text(value: Any) -> str:
    return str(value or "").strip()


def _plan_role_links(
    version: int,
    role: str,
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    query_date: Optional[str] = None,
    period_preset: Optional[str] = None,
    batch_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    context = build_workbench_plan_context(
        version=version,
        plan_role=role,
        date_from=date_from,
        date_to=date_to,
        query_date=query_date,
        period_preset=period_preset,
        batch_id=batch_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return [
        build_workbench_link(context, "gantt", label="设备甘特图", view="machine"),
        build_workbench_link(context, "gantt", label="人员甘特图", view="operator"),
        build_workbench_link(context, "week_plan", label="周计划"),
        build_workbench_link(context, "resource_dispatch", label="资源排班"),
        build_workbench_link(context, "overdue_report", label="超期清单"),
    ]


def build_version_picker_gantt_links(
    services: Any,
    version: Optional[int],
    *,
    plan_role: str,
    scenario_id: Optional[str],
    back_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """版本选择器两条甘特链接（fusion-handrolled-links-adoption）。

    用全量方案身份建 context：场景预览通过公开 plan_context_token 跳甘特，
    不再掉回正式视角（roadmap 第 11 条点名的真实缺陷）；裸 preview 无 scenario_id
    由合同禁用并明示。resolve 的 ValidationError 穿透——路由对相同参数的
    publish 调用已是同样行为，不引入第二套容错口径。
    """
    if version is None:
        return []
    from .scheduler_navigation_publish import resolve_navigation_plan_context

    plan_resolution = resolve_navigation_plan_context(services, int(version), plan_role, scenario_id)
    effective_role = str(plan_resolution.get("selected_role") or plan_role or "")
    effective_scenario = plan_resolution.get("scenario_id") or scenario_id
    plan_query_service = getattr(services, "schedule_plan_query_service", None)
    span = None
    span_error = ""
    span_error_message = "这个版本的计划日期范围读取失败，暂时不能从这里跳转甘特图。"
    try:
        span = get_plan_time_span_dates(plan_query_service, int(version), effective_role, effective_scenario)
    except ValidationError:
        # 预期的数据缺失（版本无明细/日期跨度不可解）：链接禁用并友好提示，不渲染错数据
        span_error = span_error_message
    except Exception:
        # 非预期错误（如 plan_query_service 未注入、编程错误）：同样降级禁用链接，但必须留
        # 日志——不静默吞掉真因（项目惯例：宽 except 必配 logger.exception），便于排查
        current_app.logger.exception(
            "甘特链接日期跨度读取异常 version=%s role=%s", version, effective_role
        )
        span_error = span_error_message
    context = build_workbench_plan_context(
        version=int(version),
        plan_role=effective_role,
        plan_resolution=plan_resolution,
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
        scenario_id=effective_scenario,
        plan_context_token=plan_context_token(effective_scenario),
        date_from=(span or {}).get("start_date"),
        date_to=(span or {}).get("end_date"),
        back_to=back_to,
    )
    if span_error:
        context["plan_time_span_load_error"] = span_error
    return [
        build_workbench_link(context, "gantt", label="查看设备甘特图", view="machine"),
        build_workbench_link(context, "gantt", label="查看人员甘特图", view="operator"),
    ]


def attach_candidate_plan_links(
    ctx: Dict[str, Any],
    selected_ver: Optional[int],
    *,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    query_date: Optional[str] = None,
    period_preset: Optional[str] = None,
    batch_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> None:
    display = ctx.get("candidate_comparison_display")
    if selected_ver is None or not isinstance(display, dict):
        return
    for row in list(display.get("rows") or []):
        if not isinstance(row, dict) or not row.get("plan_role_available") or not row.get("can_open_detail"):
            continue
        role = str(row.get("role") or "").strip()
        if not role:
            continue
        row["links"] = _plan_role_links(
            int(selected_ver),
            role,
            date_from=date_from,
            date_to=date_to,
            query_date=query_date,
            period_preset=period_preset,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )


__all__ = ["attach_candidate_plan_links", "build_version_picker_gantt_links"]
