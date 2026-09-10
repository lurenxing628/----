"""Dormant legacy GET adapter. No route mount, database open, write or ref repair."""

from dataclasses import replace
from urllib.parse import urlencode

from werkzeug.exceptions import NotFound

from core.errors import AppError
from core.models.workbench_command import canonical_json
from core.models.workbench_plan_reference import WorkbenchPlanReferenceError
from core.services.workbench.legacy_navigation_queries import LegacyNavigationQueries, LegacyNavigationSourceMissing
from web.routes.domains.scheduler.scheduler_plan_context_token import plan_context_token

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
    LegacyDownloadLink,
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
_REPORT_EXPORTS = {
    "reports.overdue_page": "/reports/overdue/export",
    "reports.utilization_page": "/reports/utilization/export",
    "reports.downtime_page": "/reports/downtime/export",
    "reports.execution_review_page": "/reports/execution-review/export",
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
    return retired(code, message or "新入口不能等价表达这组旧条件，未忽略条件后跳转。原数据和下载接口仍保留。",
                   public_context=public)


def _detail(queries, legacy, args):
    kind, key = _DETAILS[legacy.endpoint]
    if set(legacy.path_values) != {key}:
        raise LegacyNavigationInvalid("旧详情入口的路径字段不完整或存在多余字段。")
    code = legacy.path_values[key]
    if type(code) is not str or not code:
        raise LegacyNavigationInvalid("旧详情入口缺少明确对象。")
    entity = queries.entity(kind, code)
    if entity.entity_ref is None:
        return _unsupported("identity_missing", "原对象缺少永久引用，读取不会补建或换成其他对象。")
    if legacy.endpoint == "personnel.operator_calendar_page":
        return _unsupported("operator_calendar_scope_retired",
                            "原入口定位的是指定人员的专属日历；当前导航不能等价保留这份人员范围，未改查公共日历或其他人员。")
    if args:
        return _unsupported()
    context = {"entity_ref": entity.entity_ref}
    if kind == "batch":
        return _redirect("batches", context)
    context.update(source="production", kind=kind)
    if kind == "op_type":
        context["category"] = entity.category
    return _redirect("process", context)


def _download_links(endpoint, args, plan):
    allowed = IDENTITY_KEYS | RESOURCE_KEYS | {"date_from", "date_to", "start_date", "end_date", "batch_id"}
    if endpoint not in _REPORT_EXPORTS or set(args) - allowed or plan.fallback:
        return ()
    if endpoint == "reports.execution_review_page" and (plan.locator.plan_role != "adopted" or plan.locator.scenario_id is not None):
        return ()
    query = {key: value for key, value in args.items() if key not in ("scenario_id", "plan_context_token")}
    query.update(version=str(plan.locator.version), plan_role=plan.locator.plan_role)
    if plan.locator.scenario_id is not None:
        query["plan_context_token"] = plan_context_token(plan.locator.scenario_id)
    return (LegacyDownloadLink("按原条件下载旧报表", _REPORT_EXPORTS[endpoint] + "?" + urlencode(query)),)


def _plan_page(queries, legacy, args):
    plan = resolve_legacy_plan(queries, args)
    public = dict(plan.public_context)
    resource = resource_filter(args)
    if plan.fallback:
        return _unsupported("requested_role_unavailable", "所选对比方案未保存，未沿用旧页的采用方案回退。", public)
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
                            "旧分析页的日期和资源条件用于关联入口，不能当成新分析筛选范围，未改写原条件。", public)
    dates = report_dates(args)
    if dates:
        public["原日期条件"] = " 至 ".join(dates)
    if resource[0]:
        public["资源维度"] = "设备" if resource[0] == "machine" else "人员"
    result = _unsupported("old_scope_not_equivalent",
                          "原页面的统计、日期或资源口径不能由当前导航完整表达，未改用新报表默认范围。", public)
    return replace(result, links=_download_links(legacy.endpoint, args, plan))


def _resolve(queries, legacy, args):
    policy = PAGE_POLICIES[legacy.endpoint]
    if policy == "restyle":
        return LegacyGetDecision("restyle")
    if legacy.endpoint in _DETAILS:
        return _detail(queries, legacy, args)
    if legacy.path_values:
        raise LegacyNavigationInvalid("旧页面包含未支持的路径条件。")
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
        raise NotFound("原对象或排产版本不存在，未选择其他对象。") from exc
    except WorkbenchPlanReferenceError:
        return _unsupported("identity_unavailable", "原计划的永久身份缺失或绑定已失效，未补建身份或换查其他计划。")
    except (ValueError, AppError, OverflowError) as exc:
        invalid_plan_input(exc)
