from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.models.execution_review_identity import can_read_execution_review
from core.services.report import ReportEngine
from web.routes.report_plan_preview import page_date_range_or_version_span, page_plan_resolution
from web.routes.reports_execution_review_context import (
    blocked_execution_review_plan_resolution,
    execution_review_context_overrides,
)
from web.routes.reports_export_support import current_report_export_url
from web.routes.reports_page_support import (
    _decorated_versions,
    _publish_report_context,
    _request_text,
    _version_or_none,
)
from web.routes.reports_plan_template_fields import report_plan_template_fields
from web.routes.reports_request_support import (
    execution_review_plan_identity_error,
    request_plan_role,
    request_resource_filter,
    request_scenario_id,
)
from web.viewmodels.scheduler_reports_workbench import (
    build_report_limitations,
    build_report_page_links,
    decorate_execution_review_rows,
)


def _paired_execution_dates() -> Tuple[str, str]:
    raw_date_from = _request_text("date_from", "start_date")
    raw_date_to = _request_text("date_to", "end_date")
    if bool(raw_date_from) != bool(raw_date_to):
        raise ValidationError("开始日期和结束日期要一起填写。", field="date_from")
    return raw_date_from, raw_date_to


def _execution_review_report(
    engine: ReportEngine,
    version: Any,
    date_from: str,
    date_to: str,
    batch_id: str,
    resource_type: str,
    resource_id: str,
    *,
    enforce_date_range_limit: bool = True,
) -> Dict[str, Any]:
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
        enforce_date_range_limit=enforce_date_range_limit,
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


def _execution_review_export_url(rep: Dict[str, Any], *, date_source: str = "") -> str:
    fields = _execution_review_text_fields(rep)
    date_params = {}
    if date_source != "version_span":
        date_params = {"date_from": fields["date_from"], "date_to": fields["date_to"]}
    return current_report_export_url(
        "reports.execution_review_export",
        version=rep.get("version"),
        batch_id=fields["batch_id"],
        **date_params,
    )


def execution_review_page_context(engine: ReportEngine, services) -> Dict[str, Any]:
    versions = _decorated_versions(engine)
    version = _version_or_none(engine)
    raw_plan_role = request_plan_role()
    scenario_id = request_scenario_id()
    identity_error = execution_review_plan_identity_error(raw_plan_role, scenario_id)
    plan_resolution = page_plan_resolution(services.schedule_plan_query_service, version, "adopted", None)
    if not identity_error and not can_read_execution_review(plan_resolution):
        identity_error = str(plan_resolution.get("plan_identity_error") or "").strip() or "当前版本不能生成计划和现场实际复盘。"
    raw_date_from, raw_date_to = _paired_execution_dates()
    date_from, date_to, date_source, _span = page_date_range_or_version_span(
        engine,
        int(version or 0),
        "adopted",
        None,
        raw_date_from,
        raw_date_to,
    )
    batch_id = _request_text("batch_id")
    resource_type, resource_id = request_resource_filter()
    rep = (
        _blocked_execution_review_report(version, date_from, date_to, batch_id)
        if identity_error
        else _execution_review_report(
            engine,
            version,
            date_from,
            date_to,
            batch_id,
            resource_type,
            resource_id,
            enforce_date_range_limit=date_source == "query",
        )
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
        capsule_rows=versions,
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
        "execution_review_export_url": "" if identity_error else _execution_review_export_url(rep, date_source=date_source),
    }


__all__ = ["execution_review_page_context"]
