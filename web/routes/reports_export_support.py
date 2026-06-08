from __future__ import annotations

import time
from typing import Any, Optional

from flask import g, request, send_file, url_for

from core.services.common.excel_audit import log_excel_export
from core.services.report import ReportEngine
from core.services.report.report_number_parsing import parse_report_nonnegative_int
from web.routes.report_plan_preview import report_export_filters

_EXPORT_CONTEXT_KEYS = (
    "back_to",
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


def _has_text(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def current_report_export_url(endpoint: str, **base_params: Any) -> str:
    params = {key: value for key, value in base_params.items() if _has_text(value)}
    for key in _EXPORT_CONTEXT_KEYS:
        if key not in params and _has_text(request.args.get(key)):
            params[key] = request.args.get(key)
    return url_for(endpoint, **params)


def report_nonnegative_int(value: Any, *, field: str) -> int:
    return parse_report_nonnegative_int(value, field=field, label=field, source_label="报表导出数据")


def send_report_export_file(report_export: Any):
    resp = send_file(
        report_export.data,
        as_attachment=True,
        download_name=report_export.filename,
        mimetype=report_export.content_type,
    )
    mode = str(getattr(report_export, "mode", "direct") or "direct").strip() or "direct"
    estimated_rows = report_nonnegative_int(getattr(report_export, "estimated_rows", 0), field="导出行数")
    resp.headers["X-APS-Report-Export-Mode"] = mode
    resp.headers["X-APS-Report-Estimated-Rows"] = str(estimated_rows)
    return resp


def log_report_export(
    *,
    engine: ReportEngine,
    report_export: Any,
    target_type: str,
    export_type: str,
    version: int,
    raw_plan_role: Any,
    scenario_id: Optional[str] = None,
    time_range: Optional[dict] = None,
    started_at: float,
) -> None:
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="reports",
        target_type=target_type,
        template_or_export_type=export_type,
        filters=report_export_filters(engine, int(version), raw_plan_role, scenario_id),
        row_count=report_nonnegative_int(getattr(report_export, "estimated_rows", 0), field="导出行数"),
        time_range=time_range or {},
        time_cost_ms=int((time.time() - started_at) * 1000),
        target_id=str(version),
    )


__all__ = ["current_report_export_url", "log_report_export", "report_nonnegative_int", "send_report_export_file"]
