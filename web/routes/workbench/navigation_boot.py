"""Strict URL navigation input only; no routing, database lookup or default identity."""

from __future__ import annotations

import json
import re
from dataclasses import fields
from typing import Any, Dict, NoReturn, Optional

from core.errors import AppError
from core.models.workbench_batch_query import batch_scope
from core.models.workbench_calendar import calendar_date
from core.models.workbench_command import canonical_json
from core.models.workbench_plan_scope import PlanReadScope, local_time, plan_reference
from core.models.workbench_report import TOPICS, ReportScope
from core.models.workbench_run_job import validate_run_ref
from core.models.workbench_trial import create_input, reference

SUPPORTED_VIEWS = frozenset((
    "dashboard", "process", "batches", "run", "analysis", "gantt", "delay", "field", "fieldgantt",
    "review", "reports", "calib", "basedata", "system", "trial",
))
EMPTY_CONTEXT_VIEWS = frozenset(("dashboard", "field", "fieldgantt", "calib", "basedata", "system"))
_RESOURCE_KINDS = frozenset(("material", "op_type", "machine", "operator", "supplier", "part", "calendar"))


class WorkbenchNavigationInvalid(ValueError):
    """Invalid explicit navigation must not become another object or a wider scope."""


def _invalid(message: str) -> NoReturn:
    raise WorkbenchNavigationInvalid(message)


def _object(value, allowed, required=()):
    if type(value) is not dict or set(value) - set(allowed) or not set(required) <= set(value):
        _invalid("页面地址里的定位内容不完整或有不支持的项，页面没有打开，也没有丢掉任何条件。请从侧栏重新进入。")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _invalid("页面地址里的定位内容有重复项，页面没有打开；系统没有替你挑一个继续。请从侧栏重新进入。")
        result[key] = value
    return result


def _invalid_constant(_value):
    _invalid("页面地址里的数字不是有效数字，页面没有打开。请从侧栏重新进入。")


def _query_value(view, args):
    if set(args) - {"nav", "view"}:
        _invalid("页面地址里有不支持的条件，页面没有打开。请从侧栏重新进入。")
    for key in args:
        values = args.getlist(key) if hasattr(args, "getlist") else [args[key]]
        if len(values) != 1 or type(values[0]) is not str:
            _invalid("页面地址里的条件有重复项或格式不对，页面没有打开。请从侧栏重新进入。")
    if "view" in args and args["view"] != view:
        _invalid("页面地址里的定位内容不属于当前页面，页面没有打开。请从侧栏重新进入。")
    if "nav" not in args:
        return None
    if not args["nav"]:
        _invalid("页面地址里没有定位内容，页面没有打开；系统没有恢复上次选择，也没有改查默认记录。请从侧栏重新进入。")
    return args["nav"]


def _plan_context(context):
    _object(context, ("plan_ref", "range_start", "range_end"), ("plan_ref",))
    PlanReadScope(**context)
    _explicit_times(context)


def _explicit_times(scope):
    if "range_start" in scope or "range_end" in scope:
        local_time(scope.get("range_start"))
        local_time(scope.get("range_end"))


def _calendar_context(context):
    _object(context, ("source", "kind", "month", "date"), ("source", "kind", "month"))
    month = context["month"]
    if type(month) is not str or re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None:
        _invalid("页面地址里的月份不对，页面没有打开。请从侧栏进入「工作日历」重新选择月份。")
    calendar_date(month + "-01")
    if "date" in context and calendar_date(context["date"])[:7] != month:
        _invalid("页面地址里的日期不在这个月里，页面没有打开。请从侧栏进入「工作日历」重新选择日期。")


def _resource_context(context):
    if context.get("source") != "production":
        _invalid("页面地址没有指明要看生产资料，页面没有打开。请从侧栏进入「基础资料」重新选择。")
    if set(context) == {"source"}:
        return
    kind = context.get("kind")
    if type(kind) is not str or kind not in _RESOURCE_KINDS:
        _invalid("页面地址里的资料类别不支持，页面没有打开。请从侧栏进入「基础资料」重新选择。")
    if kind == "calendar":
        _calendar_context(context)
        return
    extra = ("category",) if kind == "op_type" else ()
    if kind == "part":
        extra = ("stage", "template_operation_ref", "template_external_group_ref")
    _object(context, ("source", "kind", "entity_ref") + extra, ("source", "kind", "entity_ref"))
    reference(context["entity_ref"])
    if kind == "op_type" and context.get("category") not in ("internal", "external"):
        _invalid("看工种要先指明自制还是外协，页面没有打开。请从侧栏进入「基础资料」重新选择。")
    _part_context(context, kind)


def _part_context(context, kind):
    if kind != "part":
        return
    if "stage" in context and context["stage"] not in ("route", "source", "hours"):
        _invalid("页面地址里的工艺阶段不对，页面没有打开。请从侧栏进入「基础资料」重新选择。")
    for key in ("template_operation_ref", "template_external_group_ref"):
        if key in context:
            reference(context[key])


def _batch_context(context):
    _object(context, ("entity_ref", "focus", "batchIds"))
    if "entity_ref" in context:
        reference(context["entity_ref"])
    scope = {"focus": context["focus"]} if "focus" in context else {}
    if "batchIds" in context:
        scope["batch_ids"] = context["batchIds"]
    batch_scope(scope)


def _report_context(context, view):
    allowed = ("scope", "topic", "catalogOpen") if view == "reports" else ("scope",)
    _object(context, allowed, ("scope",))
    scope = context["scope"]
    names = tuple(item.name for item in fields(ReportScope))
    _object(scope, names + ("kind",), ("plan_ref",))
    if "kind" in scope and scope["kind"] != "execution_analysis":
        _invalid("页面地址里的报表范围不对，页面没有打开；系统没有替你换统计范围。请从侧栏进入「报表中心」重新选择。")
    plan_reference(scope["plan_ref"])
    ReportScope(**{key: value for key, value in scope.items() if key != "kind"})
    if "topic" in context and context["topic"] not in TOPICS:
        _invalid("页面地址里的报表专题不支持，页面没有打开。请从侧栏进入「报表中心」重新选择。")
    if "catalogOpen" in context and type(context["catalogOpen"]) is not bool:
        _invalid("页面地址里报表列表的展开状态填写不对，页面没有打开。请从侧栏进入「报表中心」重新进入。")


def _trial_task_origin(context):
    _object(context, ("base", "scope", "draft_ref", "task_origin"), ("task_origin",))
    origin = context["task_origin"]
    keys = ("plan_ref", "operation_ref", "task_ref")
    _object(origin, keys, keys)
    for key in keys:
        reference(origin[key])
    target = {key: value for key, value in context.items() if key != "task_origin"}
    if set(target) == {"draft_ref"}:
        reference(target["draft_ref"])
        return
    create_input(target)
    _explicit_times(target.get("scope", {}))
    if target["base"] != {"plan_ref": origin["plan_ref"]}:
        _invalid("要定位的工序必须属于同一份计划，不能换成候选方案或别的计划，页面没有打开。请从侧栏进入「试调」重新选择。")


def _trial_context(context):
    if "task_origin" in context:
        _trial_task_origin(context)
    elif set(context) in ({"draft_ref"}, {"scenario_ref"}):
        reference(next(iter(context.values())))
    else:
        create_input(context)
        _explicit_times(context.get("scope", {}))


def _context(view, context):
    if type(context) is not dict:
        _invalid("页面地址里的定位内容格式不对，页面没有打开。请从侧栏重新进入。")
    if not context:
        return
    if view in EMPTY_CONTEXT_VIEWS:
        _invalid("这个页面还不支持用网址定位，页面没有打开，也没有丢掉传入的条件。请从侧栏重新进入。")
    if view in ("gantt", "analysis", "delay"):
        _plan_context(context)
    elif view == "process":
        _resource_context(context)
    elif view == "batches":
        _batch_context(context)
    elif view in ("reports", "review"):
        _report_context(context, view)
    elif view == "run":
        _object(context, ("run_ref",), ("run_ref",))
        validate_run_ref(context["run_ref"])
    elif view == "trial":
        _trial_context(context)


def read_navigation(view: str, args: Any) -> Optional[Dict[str, Any]]:
    """Read request.args without flattening; absent nav is not an explicit target.

    Existing domain readers remain responsible for ref existence and binding.
    This function must never query, repair, or substitute a missing identity.
    """
    try:
        raw = _query_value(view, args)
        if raw is None:
            return None
        value = json.loads(raw, object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
        _object(value, ("version", "view", "context"), ("version", "view", "context"))
        if type(value["version"]) is not int or value["version"] != 1:
            _invalid("页面地址里的定位版本不支持，页面没有打开。请从侧栏重新进入。")
        if type(view) is not str or view not in SUPPORTED_VIEWS or value["view"] != view:
            _invalid("页面地址里的定位目标不属于当前页面，页面没有打开。请从侧栏重新进入。")
        _context(view, value["context"])
        canonical_json(value).encode("utf-8")
        return value
    except WorkbenchNavigationInvalid:
        raise
    except (ValueError, TypeError, AppError, RecursionError) as exc:
        raise WorkbenchNavigationInvalid("页面地址里的定位或范围不对，页面没有打开；系统没有恢复上次选择，也没有换记录或放宽范围。请从侧栏重新进入。") from exc
