from __future__ import annotations

import math
import time

from flask import Blueprint, g, request, send_file

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.common.excel_audit import log_excel_export
from core.services.report import ReportEngine
from core.services.scheduler.version_resolution import (
    VersionResolution,
    require_selected_version,
    resolve_version_or_latest,
)
from web.routes.history_summary_logging import log_history_version_option_parse_warnings
from web.routes.report_plan_preview import (
    export_date_range_or_version_span,
    page_date_range_or_version_span,
    page_plan_resolution,
    reject_scenario_export,
    report_export_filters,
    request_scenario_id,
)
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options

bp = Blueprint("reports", __name__)


def _export_version_or_latest(engine: ReportEngine) -> int:
    """
    导出接口的 version 解析规则：
    - version 缺失/空字符串/latest：回落到最新版本（与页面默认口径一致）
    - 显式非法 version（无法转 int/<=0）：按页面统一合同抛出校验错误
    - 若无排产历史，latest_version() 可能为 0（保持现状）
    """
    resolution = _resolve_report_version(engine, request.args.get("version"))
    if resolution.status == "missing_history":
        return require_selected_version(resolution)
    return require_selected_version(resolution, message="暂无排产历史，无法导出报表。")


def _resolve_report_version(engine: ReportEngine, raw_version) -> VersionResolution:
    latest = int(engine.latest_version() or 0)
    return resolve_version_or_latest(
        raw_version,
        latest_version=latest,
        version_exists=lambda version: engine.history_repo.get_by_version(int(version)) is not None,
    )


def _page_version_or_latest(engine: ReportEngine) -> VersionResolution:
    resolution = _resolve_report_version(engine, request.args.get("version"))
    if resolution.status == "missing_history":
        raise BusinessError(
            ErrorCode.NOT_FOUND,
            "排产版本不存在，请先选择已有版本。",
            details={"field": "version", "requested_version": resolution.requested_version, "status": resolution.status},
        )
    return resolution


def _request_plan_role():
    return request.args.get("plan_role")


def _request_scenario_id():
    return request_scenario_id(request.args)


def _send_report_export_file(report_export):
    resp = send_file(
        report_export.data,
        as_attachment=True,
        download_name=report_export.filename,
        mimetype=report_export.content_type,
    )
    mode = str(getattr(report_export, "mode", "direct") or "direct").strip() or "direct"
    estimated_rows = _report_nonnegative_int(getattr(report_export, "estimated_rows", 0), field="导出行数")
    resp.headers["X-APS-Report-Export-Mode"] = mode
    resp.headers["X-APS-Report-Estimated-Rows"] = str(estimated_rows)
    return resp


def _report_number(value, *, field: str) -> float:
    if value is None or (isinstance(value, str) and value.strip() == ""):
        return 0.0
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValidationError(f"{field} 数据异常，无法生成报表。", field=field) from exc
    if not math.isfinite(number):
        raise ValidationError(f"{field} 数据异常，无法生成报表。", field=field)
    return number


def _report_nonnegative_int(value, *, field: str) -> int:
    number = _report_number(value, field=field)
    if not number.is_integer():
        raise ValidationError(f"{field} 数据异常，无法生成报表。", field=field)
    return max(0, int(number))


def _log_report_export(
    *,
    engine: ReportEngine,
    report_export,
    target_type: str,
    export_type: str,
    version: int,
    raw_plan_role,
    time_range=None,
    started_at: float,
) -> None:
    log_excel_export(
        op_logger=getattr(g, "op_logger", None),
        module="reports",
        target_type=target_type,
        template_or_export_type=export_type,
        filters=report_export_filters(engine, int(version), raw_plan_role),
        row_count=_report_nonnegative_int(getattr(report_export, "estimated_rows", 0), field="导出行数"),
        time_range=time_range or {},
        time_cost_ms=int((time.time() - started_at) * 1000),
        target_id=str(version),
    )


def _with_utilization_percent(rows):
    out = []
    for row in list(rows or []):
        item = dict(row or {})
        raw_utilization = item.get("utilization")
        if raw_utilization is None or (isinstance(raw_utilization, str) and raw_utilization.strip() == ""):
            item["utilization_percent"] = None
        else:
            item["utilization_percent"] = round(_report_number(raw_utilization, field="利用率") * 100.0, 2)
        out.append(item)
    return out


def _sum_report_number(rows, key: str) -> float:
    total = 0.0
    for row in rows or []:
        total += _report_number((row or {}).get(key), field=key)
    return round(total, 2)


@bp.get("/")
def index():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=1)
    has_history = bool(versions)
    latest_version = versions[0] if has_history else None
    overdue_count = 0
    if has_history:
        latest_ver = int((latest_version or {}).get("version") or 0)
        rep = engine.overdue_batches(latest_ver)
        overdue_count = int(rep.get("count") or 0)
    return render_template(
        "reports/index.html",
        title="报表中心",
        has_history=has_history,
        latest_version=latest_version,
        overdue_count=overdue_count,
    )


@bp.get("/overdue")
def overdue_page():
    engine = ReportEngine(g.db)
    versions = decorate_history_version_options(engine.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="报表页")
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    raw_plan_role = _request_plan_role()
    scenario_id = _request_scenario_id()
    plan_resolution = page_plan_resolution(g.services.schedule_plan_query_service, version, raw_plan_role, scenario_id)
    rep = (
        engine.overdue_batches(int(version), plan_role=raw_plan_role, scenario_id=scenario_id)
        if version is not None
        else {"version": None, "items": [], "count": 0, "scheduled_count": 0, "unscheduled_count": 0, "as_of_time": None}
    )
    has_history = bool(versions)
    empty_reason = None
    if int(rep.get("count") or 0) <= 0:
        empty_reason = "no_history" if not has_history else "no_overdue"
    return render_template(
        "reports/overdue.html",
        title="报表 - 超期清单",
        versions=versions,
        version=rep.get("version"),
        plan_options=plan_resolution["available_roles"],
        selected_plan_role=plan_resolution["selected_role"],
        requested_plan_role=plan_resolution["requested_role"],
        plan_resolution=plan_resolution,
        scenario_id=scenario_id,
        rows=rep["items"],
        count=int(rep["count"]),
        scheduled_count=int(rep.get("scheduled_count") or 0),
        unscheduled_count=int(rep.get("unscheduled_count") or 0),
        as_of_time=rep.get("as_of_time"),
        has_history=has_history,
        empty_reason=empty_reason,
    )


@bp.get("/overdue/export")
def overdue_export():
    started_at = time.time()
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    plan_role = _request_plan_role()
    reject_scenario_export(_request_scenario_id())
    x = engine.export_overdue_xlsx(version, plan_role=plan_role)
    _log_report_export(
        engine=engine,
        report_export=x,
        target_type="overdue",
        export_type="超期清单.xlsx",
        version=version,
        raw_plan_role=plan_role,
        started_at=started_at,
    )
    return _send_report_export_file(x)


@bp.get("/utilization")
def utilization_page():
    engine = ReportEngine(g.db)
    versions = decorate_history_version_options(engine.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="报表页")
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    raw_plan_role = _request_plan_role()
    scenario_id = _request_scenario_id()
    plan_resolution = page_plan_resolution(g.services.schedule_plan_query_service, version, raw_plan_role, scenario_id)
    start_date, end_date, date_source, _span = page_date_range_or_version_span(
        engine,
        int(version or 0),
        raw_plan_role,
        scenario_id,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = (
        engine.utilization(int(version), start_date, end_date, plan_role=raw_plan_role, scenario_id=scenario_id)
        if version is not None
        else {"version": None, "start_date": start_date, "end_date": end_date, "capacity_hours_per_resource": 0, "machines": [], "operators": []}
    )
    has_history = bool(versions)
    empty_reason = None
    if not rep.get("machines") and not rep.get("operators"):
        if not has_history:
            empty_reason = "no_history"
        elif date_source == "default_7d":
            empty_reason = "no_data_default_7d"
        elif date_source == "version_span":
            empty_reason = "no_data_in_version_span"
        else:
            empty_reason = "no_data_in_query_range"
    return render_template(
        "reports/utilization.html",
        title="报表 - 资源负荷与利用率",
        versions=versions,
        version=rep.get("version"),
        plan_options=plan_resolution["available_roles"],
        selected_plan_role=plan_resolution["selected_role"],
        requested_plan_role=plan_resolution["requested_role"],
        plan_resolution=plan_resolution,
        scenario_id=scenario_id,
        start_date=rep["start_date"],
        end_date=rep["end_date"],
        capacity_hours=rep["capacity_hours_per_resource"],
        machine_rows=_with_utilization_percent(rep["machines"]),
        operator_rows=_with_utilization_percent(rep["operators"]),
        date_source=date_source,
        has_history=has_history,
        empty_reason=empty_reason,
    )


@bp.get("/utilization/export")
def utilization_export():
    started_at = time.time()
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    plan_role = _request_plan_role()
    reject_scenario_export(_request_scenario_id())
    start_date, end_date = export_date_range_or_version_span(
        engine,
        int(version or 0),
        plan_role,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )
    x = engine.export_utilization_xlsx(version, start_date, end_date, plan_role=plan_role)
    _log_report_export(
        engine=engine,
        report_export=x,
        target_type="utilization",
        export_type="资源负荷与利用率.xlsx",
        version=version,
        raw_plan_role=plan_role,
        time_range={"start": start_date, "end": end_date},
        started_at=started_at,
    )
    return _send_report_export_file(x)


@bp.get("/downtime")
def downtime_page():
    engine = ReportEngine(g.db)
    versions = decorate_history_version_options(engine.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="报表页")
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    raw_plan_role = _request_plan_role()
    scenario_id = _request_scenario_id()
    plan_resolution = page_plan_resolution(g.services.schedule_plan_query_service, version, raw_plan_role, scenario_id)
    start_date, end_date, date_source, _span = page_date_range_or_version_span(
        engine,
        int(version or 0),
        raw_plan_role,
        scenario_id,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = (
        engine.downtime_impact(int(version), start_date, end_date, plan_role=raw_plan_role, scenario_id=scenario_id)
        if version is not None
        else {"version": None, "start_date": start_date, "end_date": end_date, "machines": []}
    )
    downtime_rows = list(rep.get("machines") or [])
    downtime_summary = {
        "machine_count": len(downtime_rows),
        "downtime_hours": _sum_report_number(downtime_rows, "downtime_hours"),
        "downtime_count": int(_sum_report_number(downtime_rows, "downtime_count")),
        "schedule_overlap_hours": _sum_report_number(downtime_rows, "schedule_overlap_hours"),
        "schedule_overlap_count": int(_sum_report_number(downtime_rows, "schedule_overlap_count")),
    }
    has_history = bool(versions)
    empty_reason = None
    if not downtime_rows:
        if not has_history:
            empty_reason = "no_history"
        elif date_source == "default_7d":
            empty_reason = "no_data_default_7d"
        elif date_source == "version_span":
            empty_reason = "no_data_in_version_span"
        else:
            empty_reason = "no_data_in_query_range"
    return render_template(
        "reports/downtime.html",
        title="报表 - 停机影响统计",
        versions=versions,
        version=rep.get("version"),
        plan_options=plan_resolution["available_roles"],
        selected_plan_role=plan_resolution["selected_role"],
        requested_plan_role=plan_resolution["requested_role"],
        plan_resolution=plan_resolution,
        scenario_id=scenario_id,
        start_date=rep["start_date"],
        end_date=rep["end_date"],
        rows=downtime_rows,
        downtime_summary=downtime_summary,
        date_source=date_source,
        has_history=has_history,
        empty_reason=empty_reason,
    )


@bp.get("/downtime/export")
def downtime_export():
    started_at = time.time()
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    plan_role = _request_plan_role()
    reject_scenario_export(_request_scenario_id())
    start_date, end_date = export_date_range_or_version_span(
        engine,
        int(version or 0),
        plan_role,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )
    x = engine.export_downtime_impact_xlsx(version, start_date, end_date, plan_role=plan_role)
    _log_report_export(
        engine=engine,
        report_export=x,
        target_type="downtime",
        export_type="停机影响统计.xlsx",
        version=version,
        raw_plan_role=plan_role,
        time_range={"start": start_date, "end": end_date},
        started_at=started_at,
    )
    return _send_report_export_file(x)
