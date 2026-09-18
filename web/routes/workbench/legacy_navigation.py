"""Dormant legacy GET adapter. No route mount, database open, write or ref repair.

旧报表导出接口已随旧路由层删除（2026-09-18），退役页不再提供“按原条件下载旧报表”链接。
"""

from urllib.parse import urlencode

from werkzeug.exceptions import NotFound

from core.errors import AppError
from core.models.workbench_command import canonical_json
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.legacy_navigation_queries import LegacyNavigationQueries, LegacyNavigationSourceMissing

from .legacy_navigation_plan import (
    IDENTITY_KEYS,
    RESOURCE_KEYS,
    gantt_context,
    invalid_plan_input,
    report_dates,
    resolve_legacy_plan,
    resource_filter,
)
from .legacy_page_contract import (
    PAGE_POLICIES,
    LegacyGetDecision,
    LegacyGetRequest,
    LegacyNavigationInvalid,
    retired,
    unique_query,
)
from .navigation_boot import read_navigation

_DETAILS = {
    "equipment.detail_page": ("machine", "machine_id"),
    "personnel.detail_page": ("operator", "operator_id"),
    "personnel.operator_calendar_page": ("operator", "operator_id"),
    "process.op_type_detail": ("op_type", "op_type_id"),
    "process.part_detail": ("part", "part_no"),
    "process.supplier_detail": ("supplier", "supplier_id"),
    "scheduler.batch_detail": ("batch", "batch_id"),
}
_PLAN_PAGES = frozenset(("scheduler.gantt_page", "scheduler.analysis_page", "dashboard.index",
                         "scheduler.resource_dispatch_page", "scheduler.week_plan_page"))


def build_legacy_destination(decision):
    if decision.kind != "redirect":
        raise ValueError("Only equivalent navigation has a destination.")
    value = {"version": 1, "view": decision.view, "context": dict(decision.context)}
    query = {"view": decision.view, "nav": canonical_json(value)}
    read_navigation(decision.view, query)
    path = "/workbench/trial" if decision.view == "trial" else "/workbench"
    return path + "?" + urlencode(query)


def _redirect(view, context):
    decision = LegacyGetDecision("redirect", view=view, context=context)
    build_legacy_destination(decision)
    return decision


def _unsupported(code="unsupported_scope", message=None, public=None):
    return retired(code, message or "新页面装不下这组旧条件，没有跳转，也没有丢掉任何条件。原来的数据都还在，请从侧栏进入对应页面重新筛选。",
                   public_context=public)


def _detail(queries, legacy, args):
    kind, key = _DETAILS[legacy.endpoint]
    if set(legacy.path_values) != {key}:
        raise LegacyNavigationInvalid("旧详情地址不完整或有多余项，页面没有打开。请从侧栏重新进入。")
    code = legacy.path_values[key]
    if type(code) is not str or not code:
        raise LegacyNavigationInvalid("旧详情地址里没有指明要看哪一条记录，页面没有打开。请从侧栏重新进入。")
    entity = queries.entity(kind, code)
    if entity.entity_ref is None:
        return _unsupported("identity_missing", "这条记录还没有正式编号，页面没有打开；系统不会替你补编号，也不会换成别的记录。请从侧栏重新进入。")
    if legacy.endpoint == "personnel.operator_calendar_page":
        return _unsupported("operator_calendar_scope_retired",
                            "旧入口看的是某个人员的专属班表，新页面装不下这个范围；系统没有改查公共班表或别人。请从侧栏进入「工作日历」重新选择。")
    if args:
        return _unsupported()
    context = {"entity_ref": entity.entity_ref}
    if kind == "batch":
        return _redirect("batches", context)
    context.update(source="production", kind=kind)
    if kind == "op_type":
        context["category"] = entity.category
    return _redirect("process", context)


def _plan_page(queries, legacy, args):
    plan = resolve_legacy_plan(queries, args)
    public = dict(plan.public_context)
    resource = resource_filter(args)
    if plan.fallback:
        return _unsupported("requested_role_unavailable", "要对比的方案没有保存过，页面没有打开；系统没有改成已采用的正式计划。请从侧栏进入「选择排产方案」重新选择。", public)
    if legacy.endpoint == "scheduler.gantt_page":
        context = gantt_context(queries, plan, args)
        allowed = IDENTITY_KEYS | {"week_start", "offset_weeks", "start_date", "end_date"}
        if set(args) - allowed:
            return _unsupported(public=public)
        return _redirect("gantt", context)
    if legacy.endpoint == "scheduler.analysis_page":
        if not (set(args) - IDENTITY_KEYS):
            return _redirect("analysis", {"plan_ref": plan.plan_ref})
        return _unsupported("analysis_link_scope_not_equivalent",
                            "旧分析页的日期和设备人员条件只用来跳转，新分析页装不下，页面没有打开；原来的条件没有被改动。请从侧栏进入「选择排产方案」重新筛选。", public)
    dates = report_dates(args)
    if dates:
        public["原日期条件"] = " 至 ".join(dates)
    if resource[0]:
        public["按什么统计"] = "设备" if resource[0] == "machine" else "人员"
    result = _unsupported("old_scope_not_equivalent",
                          "旧页面的统计范围、日期和设备人员条件，新报表装不下，页面没有打开；系统没有改用新报表的默认范围。请从侧栏进入「报表中心」重新筛选。", public)
    return result


def _resolve(queries, legacy, args):
    policy = PAGE_POLICIES[legacy.endpoint]
    if policy == "restyle":
        return LegacyGetDecision("restyle")
    if legacy.endpoint == "scheduler.week_plan_print_page":
        return retired("print_page_retired", "旧周派工单打印页已退役，页面没有打开。请从侧栏进入「选择排产方案」查看周计划。")
    if legacy.endpoint in _DETAILS:
        return _detail(queries, legacy, args)
    if legacy.path_values:
        raise LegacyNavigationInvalid("旧地址里有不支持的条件，页面没有打开。请从侧栏重新进入。")
    if legacy.endpoint == "dashboard.index" and not args:
        return _redirect("dashboard", {})
    if legacy.endpoint in _PLAN_PAGES or legacy.endpoint.startswith("reports."):
        return _plan_page(queries, legacy, args)
    if legacy.endpoint in ("material.index", "material.materials_page") and not args:
        return _redirect("process", {"source": "production"})
    # Old lists have implicit status/tab defaults. A generic new landing is not equivalent.
    return _unsupported("old_control_retired" if policy == "retired" else "unsupported_scope")


def resolve_legacy_get(conn, legacy):
    """Return None for non-page endpoints, so downloads/JSON/health stay untouched.

    Caller supplies the existing connection. The read snapshot respects an outer
    transaction and never allocates or repairs a persistent identity.
    """
    if not isinstance(legacy, LegacyGetRequest):
        raise TypeError("Legacy navigation requires the explicit request contract.")
    if legacy.endpoint not in PAGE_POLICIES:
        return None
    args = unique_query(legacy.query)
    queries = LegacyNavigationQueries(conn)
    try:
        with queries.read_snapshot():
            return _resolve(queries, legacy, args)
    except LegacyNavigationSourceMissing as exc:
        raise NotFound("要找的记录或排产版本不存在，页面没有打开；系统没有替你换成别的记录。请从侧栏重新进入。") from exc
    except WorkbenchPlanReferenceError:
        return _unsupported("identity_unavailable", "这份计划还没有正式编号，或编号已经失效，页面没有打开；系统不会替你补编号，也不会换查别的计划。请从侧栏进入「选择排产方案」重新选择。")
    except (ValueError, AppError, OverflowError) as exc:
        invalid_plan_input(exc)
