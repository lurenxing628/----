from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import urlencode

from core.models.schedule_resource_filter import SUPPORTED_SCHEDULE_RESOURCE_TYPES

from .scheduler_workbench_link_query import (
    ordered_required_params,
    query_for_target,
    target_uses_primary_resource_filter,
)

ROLE_ADOPTED = "adopted"

TARGET_PAGE_PATHS = {
    "dashboard": "/",
    "analysis": "/scheduler/analysis",
    "gantt": "/scheduler/gantt",
    "week_plan": "/scheduler/week-plan",
    "resource_dispatch": "/scheduler/resource-dispatch",
    "overdue_report": "/reports/overdue",
    "delay_diagnosis": "/reports/overdue",
    "utilization_report": "/reports/utilization",
    "execution_review": "/reports/execution-review",
    "downtime_report": "/reports/downtime",
    "reports_index": "/reports/",
}

_TARGET_DEFAULT_LABELS = {
    "dashboard": "回到计划工作台",
    "analysis": "查看排产分析",
    "gantt": "查看甘特图",
    "week_plan": "查看周计划",
    "resource_dispatch": "查看资源排班",
    "overdue_report": "查看超期清单",
    "delay_diagnosis": "查看延期说明",
    "utilization_report": "查看资源负荷",
    "execution_review": "查看计划和现场实际",
    "downtime_report": "查看停机影响",
    "reports_index": "查看报表中心",
}

_PLAN_ROLE_LABELS = {
    "adopted": "正式采用方案",
    "baseline_best": "原算法代表方案",
    "critical_best": "重点工序优先代表方案",
}

_GUARDRAIL_REASON_LABELS = {
    "plan_not_writable": "当前方案不可写",
    "task_state_blocked": "当前任务状态不可写",
    "action_unavailable": "后端暂未开放这个动作",
    "data_gap": "数据不足，暂时不能判断",
}

_RESOURCE_TYPE_LABELS = {
    "operator": "人员视角",
    "machine": "设备视角",
    "team": "班组视角",
}

_PERIOD_PRESET_LABELS = {
    "week": "按周",
    "month": "按月",
    "custom": "自定义",
}

_VIEW_LABELS = {
    "machine": "设备甘特",
    "operator": "人员甘特",
}

_VERSION_REQUIRED_TARGETS = {
    "analysis",
    "gantt",
    "week_plan",
    "resource_dispatch",
    "overdue_report",
    "delay_diagnosis",
    "utilization_report",
    "execution_review",
    "downtime_report",
    "reports_index",
}

_DATE_RANGE_REQUIRED_TARGETS = {
    "gantt",
    "week_plan",
    "resource_dispatch",
    "overdue_report",
    "delay_diagnosis",
    "utilization_report",
    "execution_review",
    "downtime_report",
    "reports_index",
}

def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    return value is not None and _text(value) != ""


def plan_role_label(value: Any, *, is_preview: bool = False, scenario_display_label: str = "") -> str:
    if is_preview:
        return _text(scenario_display_label) or "模拟预览（未命名）"
    text = _text(value) or ROLE_ADOPTED
    return _PLAN_ROLE_LABELS.get(text, text)


def guardrail_reason_label(value: Any) -> str:
    text = _text(value)
    return _GUARDRAIL_REASON_LABELS.get(text, text)


def resource_type_label(value: Any) -> str:
    text = _text(value)
    return _RESOURCE_TYPE_LABELS.get(text, text)


def period_preset_label(value: Any) -> str:
    text = _text(value)
    return _PERIOD_PRESET_LABELS.get(text, text)


def gantt_view_label(value: Any) -> str:
    text = _text(value)
    return _VIEW_LABELS.get(text, text)


def _preview_context(is_preview: bool, scenario_id: Any, scenario_display_label: str) -> Tuple[Optional[str], bool, str]:
    scenario_text = _text(scenario_id) or None
    preview = bool(is_preview or scenario_text)
    scenario_label = _text(scenario_display_label)
    if scenario_label:
        return scenario_text, preview, scenario_label
    if preview:
        return scenario_text, preview, "模拟预览（未命名）"
    return scenario_text, preview, ""


def _feedback_guard_context(
    *,
    plan_role_text: str,
    preview: bool,
    can_write_feedback: Optional[bool],
    guardrail_text: str,
    guardrail_reason_type: str,
) -> Tuple[bool, str, str]:
    formal_adopted = plan_role_text == ROLE_ADOPTED and not preview
    can_write = bool(can_write_feedback and formal_adopted)
    reason_type = _text(guardrail_reason_type) or ("" if can_write else "plan_not_writable")
    guardrail = _text(guardrail_text) or ("当前方案可写现场记录。" if can_write else "当前方案只能查看，不能写现场记录。")
    return can_write, guardrail, reason_type


def _public_plan_role_label(
    *,
    plan_role_text: str,
    plan_role_label_value: str,
    preview: bool,
    scenario_label: str,
) -> str:
    return _text(plan_role_label_value) or plan_role_label(
        plan_role_text,
        is_preview=preview,
        scenario_display_label=scenario_label,
    )


def _public_version_label(version: Any, version_label: str) -> str:
    explicit_label = _text(version_label)
    if explicit_label:
        return explicit_label
    if _has_value(version):
        return f"v{version}"
    return "暂无排产版本"


def build_workbench_plan_context(
    *,
    version: Any = None,
    version_label: str = "",
    plan_id: Any = None,
    plan_role: Any = ROLE_ADOPTED,
    plan_role_label_value: str = "",
    scenario_id: Any = None,
    scenario_display_label: str = "",
    date_from: Any = None,
    date_to: Any = None,
    query_date: Any = None,
    period_preset: Any = None,
    batch_id: Any = None,
    resource_type: Any = None,
    resource_id: Any = None,
    resource_label: str = "",
    is_preview: bool = False,
    can_write_feedback: Optional[bool] = None,
    guardrail_text: str = "",
    guardrail_reason_type: str = "",
    capacity_source_label: str = "",
    capacity_gap_text: str = "",
    back_to: Any = None,
) -> Dict[str, Any]:
    plan_role_text = _text(plan_role) or ROLE_ADOPTED
    scenario_text, preview, scenario_label = _preview_context(is_preview, scenario_id, scenario_display_label)
    can_write, guardrail, reason_type = _feedback_guard_context(
        plan_role_text=plan_role_text,
        preview=preview,
        can_write_feedback=can_write_feedback,
        guardrail_text=guardrail_text,
        guardrail_reason_type=guardrail_reason_type,
    )
    public_plan_role_label = _public_plan_role_label(
        plan_role_text=plan_role_text,
        plan_role_label_value=plan_role_label_value,
        preview=preview,
        scenario_label=scenario_label,
    )
    public_version_label = _public_version_label(version, version_label)
    resource_type_text = _text(resource_type)
    resource_label_text = _text(resource_label)
    return {
        "version": version,
        "version_label": public_version_label,
        "plan_id": _text(plan_id) or None,
        "plan_role": plan_role_text,
        "plan_role_label": public_plan_role_label,
        "scenario_id": scenario_text,
        "scenario_display_label": scenario_label,
        "date_from": _text(date_from) or None,
        "date_to": _text(date_to) or None,
        "query_date": _text(query_date) or None,
        "period_preset": _text(period_preset) or None,
        "batch_id": _text(batch_id) or None,
        "resource_type": resource_type_text or None,
        "resource_type_label": resource_type_label(resource_type_text) if resource_type_text else "",
        "resource_id": _text(resource_id) or None,
        "resource_label": resource_label_text,
        "is_preview": preview,
        "can_write_feedback": can_write,
        "guardrail_text": guardrail,
        "guardrail_reason_type": reason_type,
        "guardrail_reason_label": guardrail_reason_label(reason_type) if reason_type else "",
        "capacity_source_label": _text(capacity_source_label),
        "capacity_gap_text": _text(capacity_gap_text),
        "back_to": _text(back_to) or None,
    }


def _context_summary(context: Dict[str, Any], target_page: str, view: Optional[str] = None) -> str:
    parts = [_text(context.get("version_label")), _text(context.get("plan_role_label"))]
    if context.get("date_from") and context.get("date_to"):
        parts.append(f"{context['date_from']} ～ {context['date_to']}")
    if context.get("period_preset"):
        parts.append(period_preset_label(context.get("period_preset")))
    if view:
        parts.append(gantt_view_label(view))
    if context.get("resource_label"):
        parts.append(_text(context.get("resource_label")))
    if context.get("batch_id"):
        parts.append(_text(context.get("batch_id")))
    if target_page == "execution_review":
        parts.append("只复盘正式采用方案")
    return "，".join(part for part in parts if part)


def _is_formal_adopted_context(context: Dict[str, Any]) -> bool:
    if not isinstance(context, dict):
        return False
    if context.get("is_preview") or context.get("is_scenario_preview"):
        return False
    if _text(context.get("scenario_id")):
        return False
    role_values = [
        _text(context.get(key))
        for key in ("plan_role", "requested_plan_role", "effective_plan_role")
    ]
    present_roles = [role for role in role_values if role]
    if not present_roles or any(role != ROLE_ADOPTED for role in present_roles):
        return False
    if context.get("is_comparison") or context.get("is_superseded_by_newer_version"):
        return False
    return True


def _unsupported_primary_resource_reason(context: Dict[str, Any], target_page: str, resource_type: Optional[str]) -> str:
    if not target_uses_primary_resource_filter(target_page):
        return ""
    resource_type_text = _text(resource_type or context.get("resource_type"))
    if not resource_type_text or resource_type_text in SUPPORTED_SCHEDULE_RESOURCE_TYPES:
        return ""
    label = "班组" if resource_type_text == "team" else resource_type_text
    return f"当前页面暂不支持{label}维度筛选，请切换到设备或人员后再查看。"


def _disabled_reason_for_target(context: Dict[str, Any], target_page: str, *, resource_type: Optional[str] = None) -> str:
    if target_page in _VERSION_REQUIRED_TARGETS and not _has_value(context.get("version")):
        return "还没有排产版本，先执行一次排产后再查看。"
    if target_page in _DATE_RANGE_REQUIRED_TARGETS and (
        not _has_value(context.get("date_from")) or not _has_value(context.get("date_to"))
    ):
        return "还没有确认日期范围，先选择开始日期和结束日期后再查看。"
    resource_reason = _unsupported_primary_resource_reason(context, target_page, resource_type)
    if resource_reason:
        return resource_reason
    if target_page == "execution_review" and not _is_formal_adopted_context(context):
        return "计划和现场实际只复盘正式采用方案，请切换到正式采用方案后查看。"
    return ""


def _default_manual_disabled_reason(target_page: str) -> str:
    label = _TARGET_DEFAULT_LABELS.get(target_page, "这个入口")
    return f"{label}暂时不可用，请先确认当前页面的版本、日期范围和业务对象。"


def build_workbench_link(
    context: Dict[str, Any],
    target_page: str,
    *,
    label: str = "",
    view: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Any = None,
    batch_id: Any = None,
    disabled: Optional[bool] = None,
    disabled_reason: str = "",
    extra_params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if target_page not in TARGET_PAGE_PATHS:
        raise ValueError(f"未知工作台目标页：{target_page}")
    automatic_reason = _disabled_reason_for_target(context, target_page, resource_type=resource_type)
    reason = _text(disabled_reason) or automatic_reason
    is_disabled = bool(automatic_reason) or (bool(disabled) if disabled is not None else bool(reason))
    if is_disabled and not reason:
        reason = _default_manual_disabled_reason(target_page)
    query = query_for_target(
        context,
        target_page,
        view=view,
        resource_type=resource_type,
        resource_id=resource_id,
        batch_id=batch_id,
        extra_params=extra_params,
    )
    url = ""
    if not is_disabled:
        encoded = urlencode(query)
        path = TARGET_PAGE_PATHS[target_page]
        url = f"{path}?{encoded}" if encoded else path
    return {
        "label": _text(label) or _TARGET_DEFAULT_LABELS[target_page],
        "url": url,
        "target_page": target_page,
        "context_summary": _context_summary(context, target_page, view=view),
        "disabled": is_disabled,
        "disabled_reason": reason,
        "required_params": ordered_required_params(query),
    }


def build_workbench_links(context: Dict[str, Any], specs: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    links: List[Dict[str, Any]] = []
    for index, spec in enumerate(specs):
        if not isinstance(spec, dict):
            raise ValueError(f"工作台链接配置第 {index + 1} 项必须是字典。")
        target_page = _text(spec.get("target_page"))
        if not target_page:
            raise ValueError(f"工作台链接配置第 {index + 1} 项缺少 target_page。")
        link_kwargs = dict(spec)
        link_kwargs.pop("target_page", None)
        links.append(build_workbench_link(context, target_page, **link_kwargs))
    return links


def can_emit_feedback_write_urls(plan_identity_or_context: Any) -> bool:
    if not _is_formal_adopted_context(plan_identity_or_context):
        return False
    can_write_feedback = bool(plan_identity_or_context.get("can_write_feedback"))
    if "can_dispatch" in plan_identity_or_context:
        return bool(plan_identity_or_context.get("can_dispatch")) and can_write_feedback
    return can_write_feedback


__all__ = [
    "TARGET_PAGE_PATHS",
    "build_workbench_plan_context",
    "build_workbench_link",
    "build_workbench_links",
    "can_emit_feedback_write_urls",
    "gantt_view_label",
    "guardrail_reason_label",
    "period_preset_label",
    "plan_role_label",
    "resource_type_label",
]
