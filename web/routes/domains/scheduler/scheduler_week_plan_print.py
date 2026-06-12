"""周派工单打印页路由（fusion-dispatch-print-sheet，模块 N）。

独立打印视图：复用 get_week_plan_rows 全量行（非 preview 前 50），重分组交给
week_plan_print_sheet 纯函数；模板独立不 extends base.html（纸面零侧栏/导航）。
参数错误（group_by 非法 / day 格式非法或出周）按 ValidationError 明示，
不静默回落缺省；空行集渲染页内空态+返回链接（4.11 诚实态，不 404）。
落新文件：scheduler_week_plan.py 已 475/500，不再加码。
"""

from __future__ import annotations

from datetime import date
from typing import Any, Dict, Optional

from flask import g, render_template, request, url_for

from core.infrastructure.errors import ValidationError
from core.services.scheduler.week_plan_print_sheet import build_week_plan_print_sheets
from web.viewmodels.scheduler_history_summary import format_public_datetime

from .scheduler_bp import bp
from .scheduler_navigation_publish import requested_plan_role, resolved_scenario_id
from .scheduler_utils import get_plan_role_arg
from .scheduler_week_plan_query import (
    request_week_plan_batch_id,
    request_week_plan_resource_context,
    week_plan_data_kwargs,
)

_VALID_GROUP_BY = ("machine", "operator")

_GROUP_BY_LABELS = {"machine": "按设备", "operator": "按人员"}


def _get_group_by_arg() -> str:
    text = str(request.args.get("group_by") or "").strip() or "machine"
    if text not in _VALID_GROUP_BY:
        raise ValidationError("派工单视图不正确，请选择：按设备（machine）/ 按人员（operator）。", field="group_by")
    return text


def _get_day_arg(week_start: str, week_end: str) -> Optional[str]:
    text = str(request.args.get("day") or "").strip()
    if not text:
        return None
    try:
        day = date.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("单日日期写法不对，请填写类似 2026-06-01 的日期。", field="day") from exc
    if not (week_start <= day.isoformat() <= week_end):
        raise ValidationError(f"单日日期 {text} 不在所选周 {week_start} ～ {week_end} 内。", field="day")
    return day.isoformat()


def _identity_warning(plan_resolution: Dict[str, Any]) -> str:
    """贴旧纸误用警示（4.7 身份诚实，必须进纸面）。

    只看 selected_role/scenario_id 会漏掉「历史正式方案」（旧版本仍是 adopted
    无 scenario）——判定取 is_current_executable_official_version 为假即印。
    """
    if plan_resolution.get("is_current_executable_official_version"):
        return ""
    if plan_resolution.get("is_superseded_by_newer_version"):
        return "历史正式方案，已被新版本替代，不得下发执行"
    return "非正式方案，不得下发执行"


def _filter_scope_label(resource_context: Dict[str, Any], batch_id: Optional[str]) -> str:
    """页眉数据范围行：有筛选必须明示，防拿部分筛选的纸当全量周计划。"""
    parts = []
    if batch_id:
        parts.append(f"批次 {batch_id}")
    resource_id = str((resource_context or {}).get("resource_id") or "").strip()
    if resource_id:
        type_labels = {"machine": "设备", "operator": "人员"}
        type_label = type_labels.get(str((resource_context or {}).get("resource_type") or ""), "资源")
        parts.append(f"{type_label} {resource_id}")
    return f"仅含筛选范围：{'、'.join(parts)}" if parts else ""


def _print_page_links(*, version: Any, week_start: str, plan_resolution: Dict[str, Any],
                      resource_context: Dict[str, Any], batch_id: Optional[str],
                      group_by: str, day: Optional[str]) -> Dict[str, str]:
    common: Dict[str, Any] = {
        "version": version,
        "week_start": week_start,
        "plan_role": requested_plan_role(plan_resolution),
        "scenario_id": resolved_scenario_id(plan_resolution),
        "batch_id": batch_id,
        "resource_type": (resource_context or {}).get("resource_type"),
        "resource_id": (resource_context or {}).get("resource_id"),
    }
    common = {key: value for key, value in common.items() if str(value or "").strip()}
    other_view = "operator" if group_by == "machine" else "machine"
    switch_kwargs = dict(common, group_by=other_view)
    if day:
        switch_kwargs["day"] = day
    return {
        "back_url": url_for("scheduler.week_plan_page", **common),
        "switch_view_url": url_for("scheduler.week_plan_print_page", **switch_kwargs),
        "switch_view_label": f"切换为{_GROUP_BY_LABELS[other_view]}视图",
    }


@bp.get("/week-plan/print")
def week_plan_print_page():
    services = g.services
    week_start_arg = (request.args.get("week_start") or "").strip() or None
    group_by = _get_group_by_arg()
    svc = services.gantt_service
    wr = svc.resolve_week_range(week_start=week_start_arg, offset_weeks=0)
    week_start = wr.week_start_date.isoformat()
    week_end = wr.week_end_date.isoformat()
    day = _get_day_arg(week_start, week_end)
    resource_context = request_week_plan_resource_context()
    batch_id = request_week_plan_batch_id()

    data = svc.get_week_plan_rows(
        **week_plan_data_kwargs(
            week_start=week_start,
            offset_weeks=0,
            version=request.args.get("version"),
            plan_role=get_plan_role_arg(),
            scenario_id=str(request.args.get("scenario_id") or "").strip() or None,
            services=services,
            resource_context=resource_context,
            batch_id=batch_id,
        )
    )
    raw_resolution = data.get("plan_role_resolution")
    plan_resolution = raw_resolution if isinstance(raw_resolution, dict) else {}
    version = data.get("version")
    sheets = build_week_plan_print_sheets(data.get("rows") or [], group_by=group_by, day=day)

    history = data.get("history") if isinstance(data.get("history"), dict) else {}
    return render_template(
        "scheduler/week_plan_print.html",
        title="周派工单",
        sheets=sheets,
        version=version,
        plan_role_label=str(plan_resolution.get("user_label") or ""),
        identity_warning=_identity_warning(plan_resolution),
        generated_at_label=format_public_datetime((history or {}).get("schedule_time")),
        range_label=(f"{day}（单日）" if day else f"{week_start} ～ {week_end}"),
        filter_scope_label=_filter_scope_label(resource_context, batch_id),
        group_by_label=_GROUP_BY_LABELS[group_by],
        links=_print_page_links(
            version=version, week_start=week_start, plan_resolution=plan_resolution,
            resource_context=resource_context, batch_id=batch_id, group_by=group_by, day=day,
        ),
        has_history=bool(data.get("has_history")),
    )
