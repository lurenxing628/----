from __future__ import annotations

from typing import Any, Dict, Optional

from flask import request

from core.infrastructure.errors import ValidationError
from core.services.report import ReportEngine
from web.navigation_context import set_current_workbench_navigation_context
from web.routes.domains.scheduler.scheduler_plan_context_token import plan_context_token
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.routes.report_plan_preview import page_date_range_or_version_span, page_plan_resolution
from web.routes.reports_export_support import current_report_export_url
from web.routes.reports_plan_template_fields import report_plan_template_fields
from web.routes.reports_request_support import (
    page_version_or_latest,
    request_plan_role,
    request_resource_filter,
    request_scenario_id,
)
from web.viewmodels.plan_context_capsule import history_row_capsule_fields
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_reports_workbench import (
    ReportPresentationValueError,
    build_report_context,
    build_report_limitations,
    build_report_page_links,
    build_reports_index_workbench,
    decorate_delay_diagnosis_context,
    decorate_downtime_rows,
    decorate_overdue_rows,
    decorate_utilization_rows,
    downtime_empty_message,
    downtime_summary,
)


def _request_text(*names: str) -> str:
    for name in names:
        value = str(request.args.get(name) or "").strip()
        if value:
            return value
    return ""


def _plan_context_token_for(scenario_id: Any) -> str:
    return plan_context_token(str(scenario_id or "").strip() or None)


_OVERDUE_DATE_CONTEXT_KEYS = ("date_from", "date_to", "start_date", "end_date", "query_date", "period_preset")
def _decorated_versions(engine: ReportEngine, limit: int = 30):
    versions = decorate_history_version_options(engine.list_versions(limit=limit))
    log_history_version_option_parse_warnings(versions, log_label="报表页")
    return versions
def _version_or_none(engine: ReportEngine):
    return page_version_or_latest(engine).selected_version
def _standard_request_context(engine: ReportEngine, services, *, start_arg: str, end_arg: str) -> Dict[str, Any]:
    version = _version_or_none(engine)
    raw_plan_role = request_plan_role()
    scenario_id = request_scenario_id()
    resource_type, resource_id = request_resource_filter()
    start_date, end_date, date_source, _span = page_date_range_or_version_span(
        engine,
        int(version or 0),
        raw_plan_role,
        scenario_id,
        start_arg,
        end_arg,
    )
    return {
        "version": version,
        "raw_plan_role": raw_plan_role,
        "scenario_id": scenario_id,
        "plan_context_token": _plan_context_token_for(scenario_id),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "plan_resolution": page_plan_resolution(
            services.schedule_plan_query_service,
            version,
            raw_plan_role,
            scenario_id,
        ),
        "start_date": start_date,
        "end_date": end_date,
        "date_source": date_source,
    }
def _version_report_context(engine: ReportEngine, services) -> Dict[str, Any]:
    version = _version_or_none(engine)
    raw_plan_role = request_plan_role()
    scenario_id = request_scenario_id()
    resource_type, resource_id = request_resource_filter()
    start_date, end_date, date_source, _span = page_date_range_or_version_span(
        engine,
        int(version or 0),
        raw_plan_role,
        scenario_id,
        "",
        "",
    )
    return {
        "version": version,
        "raw_plan_role": raw_plan_role,
        "scenario_id": scenario_id,
        "plan_context_token": _plan_context_token_for(scenario_id),
        "resource_type": resource_type,
        "resource_id": resource_id,
        "plan_resolution": page_plan_resolution(
            services.schedule_plan_query_service,
            version,
            raw_plan_role,
            scenario_id,
        ),
        "start_date": start_date,
        "end_date": end_date,
        "date_source": date_source,
    }
def _publish_report_context(
    *,
    version: Any,
    plan_resolution: Dict[str, Any],
    date_from: Any,
    date_to: Any,
    batch_id: Any = None,
    resource_type: Any = None,
    resource_id: Any = None,
    capsule_rows: Any = None,
    context_overrides: Optional[Dict[str, Any]] = None,
    include_period_context: bool = True,
) -> Dict[str, Any]:
    query_date = _request_text("query_date") if include_period_context else ""
    period_preset = _request_text("period_preset") if include_period_context else ""
    context = build_report_context(
        version=version,
        plan_resolution=plan_resolution,
        plan_context_token=_plan_context_token_for((plan_resolution or {}).get("scenario_id")),
        date_from=date_from,
        date_to=date_to,
        query_date=query_date,
        period_preset=period_preset,
        batch_id=batch_id if batch_id is not None else _request_text("batch_id"),
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=str(resource_id or "").strip(),
        back_to=_request_text("back_to"),
        # 胶囊喂参：decorated 行按 version 查（查不到=空 dict→"-"诚实降级）
        **history_row_capsule_fields(capsule_rows, version))
    if context_overrides:
        context.update(context_overrides)
    set_current_workbench_navigation_context(context)
    return context
def _date_range_empty_reason(has_history: bool, date_source: str) -> str:
    if not has_history:
        return "no_history"
    if date_source == "default_7d":
        return "no_data_default_7d"
    if date_source == "version_span":
        return "no_data_in_version_span"
    return "no_data_in_query_range"
def _checked_report_value(factory: Any) -> Any:
    try:
        return factory()
    except ReportPresentationValueError as exc:
        raise ValidationError(str(exc), field=exc.field) from exc


def _export_date_params_for_context(request_ctx: Dict[str, Any], rep: Dict[str, Any]) -> Dict[str, Any]:
    if request_ctx.get("date_source") == "version_span":
        return {}
    return {"start_date": rep.get("start_date"), "end_date": rep.get("end_date")}
def reports_index_context(engine: ReportEngine, services) -> Dict[str, Any]:
    # limit=30 与子页对齐（原 limit=1 只取最新版，旧版本号进首页时胶囊查不到→错显「-」）
    versions = _decorated_versions(engine, limit=30)
    has_history = bool(versions)
    latest_version = versions[0] if has_history else None
    report_context = build_report_context(back_to=_request_text("back_to"))
    overdue_count = 0
    if has_history:
        request_ctx = _standard_request_context(
            engine, services, start_arg=_request_text("start_date", "date_from"), end_arg=_request_text("end_date", "date_to")
        )
        overdue = engine.overdue_batches(
            int(request_ctx["version"] or 0),
            plan_role=request_ctx["raw_plan_role"],
            scenario_id=request_ctx["scenario_id"],
            resource_type=request_ctx["resource_type"],
            resource_id=request_ctx["resource_id"],
            batch_id=_request_text("batch_id"),
        )
        overdue_count = int(overdue.get("count") or 0)
        report_context = _publish_report_context(
            version=request_ctx["version"],
            plan_resolution=request_ctx["plan_resolution"],
            date_from=request_ctx["start_date"],
            date_to=request_ctx["end_date"],
            resource_type=request_ctx["resource_type"],
            resource_id=request_ctx["resource_id"],
            capsule_rows=versions,
        )
    return {
        "title": "报表中心",
        "has_history": has_history,
        "latest_version": latest_version,
        "overdue_count": overdue_count,
        "reports_workbench": build_reports_index_workbench(report_context, overdue_count=overdue_count),
    }
def _overdue_report(engine: ReportEngine, request_ctx: Dict[str, Any]) -> Dict[str, Any]:
    version = request_ctx["version"]
    if version is None:
        return {"version": None, "items": [], "count": 0, "scheduled_count": 0, "unscheduled_count": 0, "as_of_time": None}
    return engine.overdue_batches(
        int(version),
        plan_role=request_ctx["raw_plan_role"],
        scenario_id=request_ctx["scenario_id"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        batch_id=_request_text("batch_id"),
    )
def overdue_page_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = _decorated_versions(engine)
    request_ctx = _version_report_context(engine, services)
    rep = _overdue_report(engine, request_ctx)
    has_history = bool(versions)
    has_rows = int(rep.get("count") or 0) > 0
    report_context = _publish_report_context(
        version=rep.get("version"),
        plan_resolution=request_ctx["plan_resolution"],
        date_from=request_ctx["start_date"],
        date_to=request_ctx["end_date"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        capsule_rows=versions,
        include_period_context=False,
    )
    raw_delay = _raw_delay_diagnosis(engine, request_ctx, has_rows)
    return {
        "title": "报表 - 超期清单",
        "versions": versions,
        "version": rep.get("version"),
        **report_plan_template_fields(request_ctx["plan_resolution"], request_ctx["scenario_id"]),
        "rows": decorate_overdue_rows(rep["items"], report_context),
        "count": int(rep["count"]),
        "scheduled_count": int(rep.get("scheduled_count") or 0),
        "unscheduled_count": int(rep.get("unscheduled_count") or 0),
        "invalid_time_count": int(rep.get("invalid_time_count") or 0),
        "invalid_due_count": int(rep.get("invalid_due_count") or 0),
        "as_of_time": rep.get("as_of_time"),
        "report_degraded": bool(rep.get("report_degraded")),
        "report_degradation_message": rep.get("report_degradation_message"),
        "report_degradation_samples": rep.get("report_degradation_samples") or [],
        "delay_diagnosis": decorate_delay_diagnosis_context(raw_delay, report_context),
        "has_history": has_history,
        "empty_reason": None if has_rows else ("no_history" if not has_history else "no_overdue"),
        "report_links": build_report_page_links(report_context),
        "report_limits": build_report_limitations("overdue"),
        "overdue_export_url": current_report_export_url(
            "reports.overdue_export",
            exclude_context_keys=_OVERDUE_DATE_CONTEXT_KEYS,
            version=rep.get("version"),
            plan_role=request_ctx["plan_resolution"]["requested_role"],
            scenario_id=request_ctx["scenario_id"],
        ),
    }
def _raw_delay_diagnosis(engine: ReportEngine, request_ctx: Dict[str, Any], has_rows: bool) -> Dict[str, Any]:
    if request_ctx["version"] is None or not has_rows:
        return {"generated_at": None, "warnings": [], "items_by_batch": {}}
    return engine.overdue_delay_diagnosis_context(
        int(request_ctx["version"]),
        plan_role=request_ctx["raw_plan_role"],
        scenario_id=request_ctx["scenario_id"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        batch_id=_request_text("batch_id"),
    )
def _utilization_report(engine: ReportEngine, request_ctx: Dict[str, Any]) -> Dict[str, Any]:
    version = request_ctx["version"]
    if version is None:
        return {
            "version": None,
            "start_date": request_ctx["start_date"],
            "end_date": request_ctx["end_date"],
            "capacity_hours_per_resource": 0,
            "machines": [],
            "operators": [],
        }
    kwargs: Dict[str, Any] = {
        "plan_role": request_ctx["raw_plan_role"],
        "scenario_id": request_ctx["scenario_id"],
        "resource_type": request_ctx["resource_type"],
        "resource_id": request_ctx["resource_id"],
        "batch_id": _request_text("batch_id"),
    }
    if request_ctx["date_source"] != "query":
        kwargs["enforce_date_range_limit"] = False
    return engine.utilization(int(version), request_ctx["start_date"], request_ctx["end_date"], **kwargs)
def utilization_page_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = _decorated_versions(engine)
    request_ctx = _standard_request_context(engine, services, start_arg=_request_text("start_date"), end_arg=_request_text("end_date"))
    rep = _utilization_report(engine, request_ctx)
    has_history = bool(versions)
    has_rows = bool(rep.get("machines") or rep.get("operators"))
    report_context = _publish_report_context(
        version=rep.get("version"),
        plan_resolution=request_ctx["plan_resolution"],
        date_from=rep["start_date"],
        date_to=rep["end_date"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        capsule_rows=versions,
    )
    machine_rows = _checked_report_value(lambda: decorate_utilization_rows(rep["machines"], report_context, resource_type="machine"))
    operator_rows = _checked_report_value(lambda: decorate_utilization_rows(rep["operators"], report_context, resource_type="operator"))
    return {
        "title": "报表 - 资源负荷与利用率",
        "versions": versions,
        "version": rep.get("version"),
        **report_plan_template_fields(request_ctx["plan_resolution"], request_ctx["scenario_id"]),
        "start_date": rep["start_date"],
        "end_date": rep["end_date"],
        "capacity_hours": rep["capacity_hours_per_resource"],
        "machine_rows": machine_rows,
        "operator_rows": operator_rows,
        "date_source": request_ctx["date_source"],
        "has_history": has_history,
        "empty_reason": None if has_rows else _date_range_empty_reason(has_history, request_ctx["date_source"]),
        "report_links": build_report_page_links(report_context),
        "report_limits": build_report_limitations("utilization"),
        "report_degraded": bool(rep.get("report_degraded")),
        "report_degradation_message": rep.get("report_degradation_message") or "",
        "report_degradation_samples": list(rep.get("report_degradation_samples") or []),
        "report_bad_time_skipped_count": int(rep.get("report_bad_time_skipped_count") or 0),
        "utilization_export_url": current_report_export_url(
            "reports.utilization_export",
            version=rep.get("version"),
            plan_role=request_ctx["plan_resolution"]["requested_role"],
            scenario_id=request_ctx["scenario_id"],
            **_export_date_params_for_context(request_ctx, rep),
        ),
    }
def _downtime_report(engine: ReportEngine, request_ctx: Dict[str, Any]) -> Dict[str, Any]:
    version = request_ctx["version"]
    if version is None:
        return {"version": None, "start_date": request_ctx["start_date"], "end_date": request_ctx["end_date"], "machines": []}
    kwargs: Dict[str, Any] = {
        "plan_role": request_ctx["raw_plan_role"],
        "scenario_id": request_ctx["scenario_id"],
        "resource_type": request_ctx["resource_type"],
        "resource_id": request_ctx["resource_id"],
        "batch_id": _request_text("batch_id"),
    }
    if request_ctx["date_source"] != "query":
        kwargs["enforce_date_range_limit"] = False
    return engine.downtime_impact(int(version), request_ctx["start_date"], request_ctx["end_date"], **kwargs)
def downtime_page_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = _decorated_versions(engine)
    request_ctx = _standard_request_context(engine, services, start_arg=_request_text("start_date"), end_arg=_request_text("end_date"))
    rep = _downtime_report(engine, request_ctx)
    downtime_rows = list(rep.get("machines") or [])
    report_context = _publish_report_context(
        version=rep.get("version"),
        plan_resolution=request_ctx["plan_resolution"],
        date_from=rep["start_date"],
        date_to=rep["end_date"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        capsule_rows=versions,
    )
    decorated_rows = decorate_downtime_rows(downtime_rows, report_context)
    summary = _checked_report_value(lambda: downtime_summary(decorated_rows))
    has_history = bool(versions)
    empty_reason = None if downtime_rows else _date_range_empty_reason(has_history, request_ctx["date_source"])
    return {
        "title": "报表 - 停机影响统计",
        "versions": versions,
        "version": rep.get("version"),
        **report_plan_template_fields(request_ctx["plan_resolution"], request_ctx["scenario_id"]),
        "start_date": rep["start_date"],
        "end_date": rep["end_date"],
        "rows": decorated_rows,
        "downtime_summary": summary,
        "date_source": request_ctx["date_source"],
        "has_history": has_history,
        "empty_reason": empty_reason,
        "downtime_empty_message": downtime_empty_message(empty_reason),
        "report_links": build_report_page_links(report_context),
        "report_limits": build_report_limitations("downtime"),
        "report_degraded": bool(rep.get("report_degraded")),
        "report_degradation_message": rep.get("report_degradation_message") or "",
        "report_degradation_samples": list(rep.get("report_degradation_samples") or []),
        "report_bad_time_skipped_count": int(rep.get("report_bad_time_skipped_count") or 0),
        "downtime_export_url": current_report_export_url(
            "reports.downtime_export",
            version=rep.get("version"),
            plan_role=request_ctx["plan_resolution"]["requested_role"],
            scenario_id=request_ctx["scenario_id"],
            **_export_date_params_for_context(request_ctx, rep),
        ),
    }
