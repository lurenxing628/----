from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from flask import request

from core.infrastructure.errors import ValidationError
from core.services.report import ReportEngine
from web.navigation_context import set_current_workbench_navigation_context
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.routes.report_plan_preview import page_date_range_or_version_span, page_plan_resolution
from web.routes.reports_execution_review_context import (
    blocked_execution_review_plan_resolution,
    execution_review_context_overrides,
)
from web.routes.reports_export_support import current_report_export_url
from web.routes.reports_plan_template_fields import report_plan_template_fields
from web.routes.reports_request_support import (
    execution_review_plan_identity_error,
    page_version_or_latest,
    request_plan_role,
    request_resource_filter,
    request_scenario_id,
)
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_reports_workbench import (
    ReportPresentationValueError,
    build_report_context,
    build_report_limitations,
    build_report_page_links,
    build_reports_index_workbench,
    decorate_delay_diagnosis_context,
    decorate_downtime_rows,
    decorate_execution_review_rows,
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


def _decorated_versions(engine: ReportEngine):
    versions = decorate_history_version_options(engine.list_versions(limit=30))
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
    context_overrides: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    context = build_report_context(
        version=version,
        plan_id=_request_text("plan_id"),
        plan_resolution=plan_resolution,
        date_from=date_from,
        date_to=date_to,
        query_date=_request_text("query_date"),
        period_preset=_request_text("period_preset"),
        batch_id=batch_id if batch_id is not None else _request_text("batch_id"),
        resource_type=resource_type,
        resource_id=resource_id,
        resource_label=str(resource_id or "").strip(),
        back_to=_request_text("back_to"),
    )
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


def reports_index_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = engine.list_versions(limit=1)
    has_history = bool(versions)
    latest_version = versions[0] if has_history else None
    report_context = build_report_context(plan_id=_request_text("plan_id"), back_to=_request_text("back_to"))
    overdue_count = 0
    if has_history:
        request_ctx = _standard_request_context(
            engine,
            services,
            start_arg=_request_text("start_date", "date_from"),
            end_arg=_request_text("end_date", "date_to"),
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
    request_ctx = _standard_request_context(
        engine,
        services,
        start_arg=_request_text("start_date", "date_from"),
        end_arg=_request_text("end_date", "date_to"),
    )
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
        "as_of_time": rep.get("as_of_time"),
        "delay_diagnosis": decorate_delay_diagnosis_context(raw_delay, report_context),
        "has_history": has_history,
        "empty_reason": None if has_rows else ("no_history" if not has_history else "no_overdue"),
        "report_links": build_report_page_links(report_context),
        "report_limits": build_report_limitations("overdue"),
        "overdue_export_url": current_report_export_url(
            "reports.overdue_export",
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
    return engine.utilization(
        int(version),
        request_ctx["start_date"],
        request_ctx["end_date"],
        plan_role=request_ctx["raw_plan_role"],
        scenario_id=request_ctx["scenario_id"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        batch_id=_request_text("batch_id"),
    )


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
    )
    machine_rows = _checked_report_value(
        lambda: decorate_utilization_rows(rep["machines"], report_context, resource_type="machine")
    )
    operator_rows = _checked_report_value(
        lambda: decorate_utilization_rows(rep["operators"], report_context, resource_type="operator")
    )
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
        "utilization_export_url": current_report_export_url(
            "reports.utilization_export",
            version=rep.get("version"),
            plan_role=request_ctx["plan_resolution"]["requested_role"],
            scenario_id=request_ctx["scenario_id"],
            start_date=rep["start_date"],
            end_date=rep["end_date"],
        ),
    }


def _paired_execution_dates() -> Tuple[str, str]:
    raw_date_from = _request_text("date_from", "start_date")
    raw_date_to = _request_text("date_to", "end_date")
    if bool(raw_date_from) != bool(raw_date_to):
        raise ValidationError("开始日期和结束日期要一起填写。", field="date_from")
    return raw_date_from, raw_date_to


def _execution_review_report(engine: ReportEngine, version: Any, date_from: str, date_to: str, batch_id: str, resource_type: str, resource_id: str) -> Dict[str, Any]:
    if version is None:
        return {
            "version": None,
            "rows": [],
            "count": 0,
            "date_from": date_from,
            "date_to": date_to,
            "batch_id": batch_id,
            "date_range_label": "全部日期",
            "batch_filter_label": batch_id or "全部批次",
        }
    return engine.execution_review(
        int(version),
        date_from=date_from,
        date_to=date_to,
        batch_id=batch_id,
        resource_type=resource_type,
        resource_id=resource_id,
    )


def _execution_review_date_label(date_from: str, date_to: str) -> str:
    if date_from and date_to:
        return f"{date_from} 至 {date_to}"
    return "全部日期"


def _blocked_execution_review_report(version: Any, date_from: str, date_to: str, batch_id: str) -> Dict[str, Any]:
    return {
        "version": version,
        "rows": [],
        "count": 0,
        "date_from": date_from,
        "date_to": date_to,
        "batch_id": batch_id,
        "date_range_label": _execution_review_date_label(date_from, date_to),
        "batch_filter_label": batch_id or "全部批次",
    }


def _execution_review_text_fields(rep: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "date_from": rep.get("date_from") or "",
        "date_to": rep.get("date_to") or "",
        "batch_id": rep.get("batch_id") or "",
        "date_range_label": rep.get("date_range_label") or "全部日期",
        "batch_filter_label": rep.get("batch_filter_label") or "全部批次",
    }


def _execution_review_empty_reason(rows: list, has_history: bool) -> Optional[str]:
    if rows:
        return None
    return "no_history" if not has_history else "no_data"


def _execution_review_export_url(rep: Dict[str, Any]) -> str:
    fields = _execution_review_text_fields(rep)
    return current_report_export_url(
        "reports.execution_review_export",
        version=rep.get("version"),
        date_from=fields["date_from"],
        date_to=fields["date_to"],
        batch_id=fields["batch_id"],
    )


def execution_review_page_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = _decorated_versions(engine)
    version = _version_or_none(engine)
    raw_plan_role = request_plan_role()
    scenario_id = request_scenario_id()
    identity_error = execution_review_plan_identity_error(raw_plan_role, scenario_id)
    plan_resolution = page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)
    raw_date_from, raw_date_to = _paired_execution_dates()
    date_from, date_to, _date_source, _span = page_date_range_or_version_span(engine, int(version or 0), "adopted", None, raw_date_from, raw_date_to)
    batch_id = _request_text("batch_id")
    resource_type, resource_id = request_resource_filter()
    rep = (
        _blocked_execution_review_report(version, date_from, date_to, batch_id)
        if identity_error
        else _execution_review_report(engine, version, date_from, date_to, batch_id, resource_type, resource_id)
    )
    context_plan_resolution = (
        blocked_execution_review_plan_resolution(plan_resolution, raw_plan_role, scenario_id)
        if identity_error
        else plan_resolution
    )
    report_context = _publish_report_context(
        version=rep.get("version"),
        plan_resolution=context_plan_resolution,
        date_from=rep.get("date_from") or "",
        date_to=rep.get("date_to") or "",
        batch_id=rep.get("batch_id") or "",
        resource_type=resource_type,
        resource_id=resource_id,
        context_overrides=execution_review_context_overrides(identity_error),
    )
    has_history = bool(versions)
    rows = list(rep.get("rows") or [])
    return {
        "title": "报表 - 计划和现场实际",
        "versions": versions,
        "version": rep.get("version"),
        **report_plan_template_fields(context_plan_resolution, None),
        **_execution_review_text_fields(rep),
        "rows": decorate_execution_review_rows(rows, report_context),
        "count": int(rep.get("count") or 0),
        "has_history": has_history,
        "empty_reason": "unsupported_plan_identity" if identity_error else _execution_review_empty_reason(rows, has_history),
        "report_links": build_report_page_links(report_context),
        "report_limits": build_report_limitations("execution_review"),
        "execution_review_identity_error": identity_error,
        "execution_review_export_url": "" if identity_error else _execution_review_export_url(rep),
    }


def _downtime_report(engine: ReportEngine, request_ctx: Dict[str, Any]) -> Dict[str, Any]:
    version = request_ctx["version"]
    if version is None:
        return {"version": None, "start_date": request_ctx["start_date"], "end_date": request_ctx["end_date"], "machines": []}
    return engine.downtime_impact(
        int(version),
        request_ctx["start_date"],
        request_ctx["end_date"],
        plan_role=request_ctx["raw_plan_role"],
        scenario_id=request_ctx["scenario_id"],
        resource_type=request_ctx["resource_type"],
        resource_id=request_ctx["resource_id"],
        batch_id=_request_text("batch_id"),
    )


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
        "downtime_export_url": current_report_export_url(
            "reports.downtime_export",
            version=rep.get("version"),
            plan_role=request_ctx["plan_resolution"]["requested_role"],
            scenario_id=request_ctx["scenario_id"],
            start_date=rep["start_date"],
            end_date=rep["end_date"],
        ),
    }
