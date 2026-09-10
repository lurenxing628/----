"""Resolve old plan inputs with existing parsers and SELECT-only permanent refs."""

from dataclasses import dataclass
from typing import Mapping

from werkzeug.exceptions import NotFound

from core.errors import AppError
from core.models.schedule_plan_role import VALID_PLAN_ROLES, _normalize_role, plan_role_label
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.services.report.date_input import validate_explicit_report_date_range
from core.services.report.report_context_filters import (
    REPORT_RESOURCE_FILTER_ARG_KEYS,
    normalize_report_resource_filter,
)
from core.services.scheduler.gantt_plan_query import resolve_gantt_range_for_version
from core.services.scheduler.version_resolution import resolve_version_or_latest
from web.routes.domains.scheduler.scheduler_plan_context_token import request_scenario_id_from_args

from .legacy_page_contract import LegacyNavigationInvalid

IDENTITY_KEYS = frozenset(("version", "plan_role", "scenario_id", "plan_context_token"))
RESOURCE_KEYS = frozenset(REPORT_RESOURCE_FILTER_ARG_KEYS)


@dataclass(frozen=True)
class ResolvedLegacyPlan:
    locator: WorkbenchPlanLocator
    plan_ref: str
    fallback: bool
    public_context: Mapping[str, str]


def _scenario(args):
    result = request_scenario_id_from_args(args)
    raw = str(args.get("scenario_id") or "").strip()
    if args.get("plan_context_token") and raw and raw != result:
        raise LegacyNavigationInvalid("方案令牌与原方案条件冲突，未选择其中一个继续。")
    return result


def resolve_legacy_plan(queries, args):
    version = resolve_version_or_latest(args.get("version"), latest_version=queries.latest_version(),
                                        version_exists=queries.version_exists)
    if version.selected_version is None:
        raise NotFound("所选排产版本不存在，未改查最新版本。")
    scenario = _scenario(args)
    role = _normalize_role(args.get("plan_role"))
    if role not in VALID_PLAN_ROLES:
        raise LegacyNavigationInvalid("原计划角色无效，未改用采用方案。")
    binding = queries.bind_plan(version.selected_version, role, scenario)
    locator = binding.locator
    public = {"排产版本": str(locator.version), "方案": plan_role_label(locator.plan_role)}
    if scenario is not None:
        public["方案范围"] = "已保存模拟方案"
    return ResolvedLegacyPlan(locator, binding.plan_ref, binding.fallback, public)


def report_dates(args):
    values = []
    for primary, alias in (("date_from", "start_date"), ("date_to", "end_date")):
        left, right = args.get(primary, "").strip(), args.get(alias, "").strip()
        if left and right:
            a, _ = validate_explicit_report_date_range(left, left)
            b, _ = validate_explicit_report_date_range(right, right)
            if a != b:
                raise LegacyNavigationInvalid("旧入口包含冲突的日期别名，未选择其中一组继续。")
        values.append(left or right)
    if any(values):
        return validate_explicit_report_date_range(*values)
    return None


def resource_filter(args):
    return normalize_report_resource_filter(**{key: args.get(key) for key in REPORT_RESOURCE_FILTER_ARG_KEYS})


def gantt_context(queries, plan, args):
    locator = plan.locator
    wr, _span, source = resolve_gantt_range_for_version(
        plan_query_service=queries, version=locator.version,
        plan_role=locator.plan_role, scenario_id=locator.scenario_id,
        week_start=args.get("week_start"), offset_weeks=args.get("offset_weeks", 0),
        start_date=args.get("start_date"), end_date=args.get("end_date"))
    context = {"plan_ref": plan.plan_ref}
    if source != "version_span":
        context.update(range_start=wr.start_dt.isoformat(timespec="seconds"),
                       range_end=wr.end_dt_exclusive.isoformat(timespec="seconds"))
    return context


def invalid_plan_input(exc):
    if isinstance(exc, (ValueError, AppError, OverflowError)):
        raise LegacyNavigationInvalid("原计划身份、日期或筛选无效，未改选对象或扩大范围。") from exc
    raise TypeError("Only domain input failures may be translated here.")
