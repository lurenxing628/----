from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlencode

from .scheduler_workbench_link_query import query_for_target
from .scheduler_workbench_links import TARGET_PAGE_PATHS, build_workbench_link, build_workbench_plan_context

ROLE_ADOPTED = "adopted"

_REPORT_CONTEXT_FIELD_NAMES = (
    "plan_id",
    "back_to",
    "scenario_id",
    "date_from",
    "date_to",
    "start_date",
    "end_date",
    "query_date",
    "period_preset",
    "batch_id",
    "resource_type",
    "resource_id",
    "scope_type",
    "scope_id",
    "machine_id",
    "operator_id",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _has_value(value: Any) -> bool:
    return value is not None and _text(value) != ""


def empty_workbench_navigation_context() -> Dict[str, Any]:
    return build_workbench_plan_context(plan_role=ROLE_ADOPTED)


def _context_or_empty(context: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    return dict(context or empty_workbench_navigation_context())


def _has_navigation_context(context: Dict[str, Any]) -> bool:
    return any(
        _has_value(context.get(key))
        for key in (
            "version",
            "plan_id",
            "date_from",
            "date_to",
            "query_date",
            "period_preset",
            "batch_id",
            "resource_type",
            "resource_id",
            "scenario_id",
            "back_to",
        )
    ) or _text(context.get("plan_role")) != ROLE_ADOPTED


def _has_navigation_date_range(context: Dict[str, Any]) -> bool:
    return _has_value(context.get("date_from")) and _has_value(context.get("date_to"))


def _use_plain_scheduler_chrome(context: Dict[str, Any], plain_scheduler_chrome: bool) -> bool:
    return bool(plain_scheduler_chrome) and not _has_navigation_context(context)


def _target_url(context: Dict[str, Any], target_page: str, *, view: Optional[str] = None) -> str:
    query = query_for_target(context, target_page, view=view)
    encoded = urlencode(query)
    path = TARGET_PAGE_PATHS[target_page]
    return f"{path}?{encoded}" if encoded else path


def _plain_link(label: str, url: str, desc: str = "", target_page: str = "") -> Dict[str, Any]:
    return {
        "label": label,
        "desc": desc,
        "url": url,
        "target_page": target_page,
        "disabled": False,
        "disabled_reason": "",
        "active": False,
    }


def _navigation_link(
    context: Dict[str, Any],
    target_page: str,
    *,
    label: str,
    desc: str = "",
    view: Optional[str] = None,
    active: bool = False,
) -> Dict[str, Any]:
    link = build_workbench_link(context, target_page, label=label, view=view)
    link["desc"] = desc
    link["active"] = active
    return link


def build_workbench_navigation_links(
    context: Optional[Dict[str, Any]] = None,
    *,
    plain_scheduler_chrome: bool = False,
) -> List[Dict[str, Any]]:
    context = _context_or_empty(context)
    if not _has_navigation_context(context) or _use_plain_scheduler_chrome(context, plain_scheduler_chrome):
        return [
            _plain_link("首页值班台", "/", "先看今天需要处理什么", "dashboard"),
            _plain_link("报表中心", "/reports/", "从风险报表继续追踪问题", "reports_index"),
            _plain_link("排产分析", "/scheduler/analysis", "看推荐方案和排产诊断", "analysis"),
            _plain_link("设备甘特图", "/scheduler/gantt?view=machine", "按设备查看排产结果", "gantt"),
            _plain_link("人员甘特图", "/scheduler/gantt?view=operator", "按人员查看排产结果", "gantt"),
            _plain_link("资源派工", "/scheduler/resource-dispatch", "看排班和现场记录入口", "resource_dispatch"),
            _plain_link("计划和现场实际", "/reports/execution-review", "复盘正式计划和现场事实", "execution_review"),
        ]
    return [
        _navigation_link(context, "dashboard", label="首页值班台", desc="先看今天需要处理什么"),
        _navigation_link(context, "reports_index", label="报表中心", desc="从风险报表继续追踪问题"),
        _navigation_link(context, "analysis", label="排产分析", desc="看推荐方案和排产诊断"),
        _navigation_link(context, "gantt", label="设备甘特图", desc="按设备查看排产结果", view="machine"),
        _navigation_link(context, "gantt", label="人员甘特图", desc="按人员查看排产结果", view="operator"),
        _navigation_link(context, "resource_dispatch", label="资源派工", desc="看排班和现场记录入口"),
        _navigation_link(context, "execution_review", label="计划和现场实际", desc="复盘正式计划和现场事实"),
    ]


def build_scheduler_navigation_links(
    context: Optional[Dict[str, Any]] = None,
    active: str = "",
    *,
    plain_scheduler_chrome: bool = False,
) -> List[Dict[str, Any]]:
    context = _context_or_empty(context)
    has_context = _has_navigation_context(context) and not _use_plain_scheduler_chrome(context, plain_scheduler_chrome)
    specs = (
        ("batches", "执行排产", "/scheduler/", None, None),
        ("batches_manage", "批次管理", "/scheduler/batches", None, None),
        ("config", "高级设置/模板", "/scheduler/config", None, None),
        ("resource_dispatch", "资源排班", "/scheduler/resource-dispatch", "resource_dispatch", None),
        ("gantt_machine", "设备甘特图", "/scheduler/gantt?view=machine", "gantt", "machine"),
        ("gantt_operator", "人员甘特图", "/scheduler/gantt?view=operator", "gantt", "operator"),
        ("analysis", "排产优化分析", "/scheduler/analysis", "analysis", None),
        ("week_plan", "周计划", "/scheduler/week-plan", "week_plan", None),
        ("calendar", "工作日历配置", "/scheduler/calendar", None, None),
    )
    links: List[Dict[str, Any]] = []
    active_key = _text(active)
    for key, label, plain_url, target_page, view in specs:
        if target_page and has_context:
            link = _navigation_link(context, target_page, label=label, view=view, active=active_key == key)
        else:
            link = _plain_link(label, plain_url or _target_url(context, str(target_page), view=view), target_page=str(target_page or key))
            link["active"] = active_key == key
        links.append(link)
    return links


def build_report_navigation_links(context: Optional[Dict[str, Any]] = None, active: str = "") -> List[Dict[str, Any]]:
    context = _context_or_empty(context)
    specs = (
        ("index", "reports_index", "报表中心"),
        ("overdue", "overdue_report", "超期清单"),
        ("utilization", "utilization_report", "资源负荷与利用率"),
        ("execution_review", "execution_review", "计划和现场实际"),
        ("downtime", "downtime_report", "停机影响统计"),
    )
    if not _has_navigation_context(context):
        return [
            _plain_link(label, TARGET_PAGE_PATHS[target], target_page=target)
            for _key, target, label in specs
        ]
    return [
        _navigation_link(context, target, label=label, active=_text(active) == key)
        for key, target, label in specs
    ]


def preserved_report_context_fields(exclude: Iterable[str] = (), *, values: Optional[Dict[str, Any]] = None) -> List[Dict[str, str]]:
    excluded = {_text(item) for item in exclude}
    source = dict(values or {})
    fields: List[Dict[str, str]] = []
    for name in _REPORT_CONTEXT_FIELD_NAMES:
        if name in excluded:
            continue
        value = _text(source.get(name))
        if value:
            fields.append({"name": name, "value": value})
    return fields


__all__ = [
    "build_report_navigation_links",
    "build_scheduler_navigation_links",
    "build_workbench_navigation_links",
    "empty_workbench_navigation_context",
    "preserved_report_context_fields",
]
