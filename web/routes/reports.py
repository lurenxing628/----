from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, g, request, send_file

from core.infrastructure.errors import BusinessError, ErrorCode, ValidationError
from core.services.report import ReportEngine
from core.services.scheduler.version_resolution import (
    VersionResolution,
    require_selected_version,
    resolve_version_or_latest,
)
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options

bp = Blueprint("reports", __name__)


def _default_date_range(days: int = 7):
    end_d = date.today()
    start_d = end_d - timedelta(days=max(0, int(days) - 1))
    return start_d.isoformat(), end_d.isoformat()


def _validate_ymd_date(raw: str, field: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValidationError("缺少开始日期或结束日期。", field="日期范围")

    s = s.replace("/", "-")
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception as e:
        raise ValidationError("日期格式不正确，请按 2026-03-13 或 2026/03/13 这样的格式填写。", field=field) from e
    return s


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


def _page_date_range_or_version_span(engine: ReportEngine, version: int, start_raw: str, end_raw: str):
    s = (start_raw or "").strip()
    e = (end_raw or "").strip()
    if s and e:
        return s, e, "query", {"has_data": False}

    span = engine.version_date_range(int(version or 0))
    if span.get("has_data") and span.get("start_date") and span.get("end_date"):
        return str(span["start_date"]), str(span["end_date"]), "version_span", span

    s7, e7 = _default_date_range(days=7)
    return s7, e7, "default_7d", span


def _send_report_export_file(report_export):
    resp = send_file(
        report_export.data,
        as_attachment=True,
        download_name=report_export.filename,
        mimetype=report_export.content_type,
    )
    mode = str(getattr(report_export, "mode", "direct") or "direct").strip() or "direct"
    try:
        estimated_rows = int(getattr(report_export, "estimated_rows", 0) or 0)
    except Exception:
        estimated_rows = 0
    resp.headers["X-APS-Report-Export-Mode"] = mode
    resp.headers["X-APS-Report-Estimated-Rows"] = str(max(0, estimated_rows))
    return resp


def _with_utilization_percent(rows):
    out = []
    for row in list(rows or []):
        item = dict(row or {})
        try:
            raw_utilization = item.get("utilization")
            if raw_utilization is None or str(raw_utilization).strip() == "":
                item["utilization_percent"] = None
            else:
                item["utilization_percent"] = round(float(raw_utilization) * 100.0, 2)
        except Exception:
            item["utilization_percent"] = None
        out.append(item)
    return out


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
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    rep = (
        engine.overdue_batches(int(version))
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
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_overdue_xlsx(version)
    return _send_report_export_file(x)


@bp.get("/utilization")
def utilization_page():
    engine = ReportEngine(g.db)
    versions = decorate_history_version_options(engine.list_versions(limit=30))
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    start_date, end_date, date_source, _span = _page_date_range_or_version_span(
        engine,
        int(version or 0),
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = (
        engine.utilization(int(version), start_date, end_date)
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
    start_raw = (request.args.get("start_date") or "").strip()
    end_raw = (request.args.get("end_date") or "").strip()
    if not start_raw or not end_raw:
        start_date, end_date = _default_date_range(days=7)
    else:
        start_date = _validate_ymd_date(start_raw, field="开始日期")
        end_date = _validate_ymd_date(end_raw, field="结束日期")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_utilization_xlsx(version, start_date, end_date)
    return _send_report_export_file(x)


@bp.get("/downtime")
def downtime_page():
    engine = ReportEngine(g.db)
    versions = decorate_history_version_options(engine.list_versions(limit=30))
    resolution = _page_version_or_latest(engine)
    version = resolution.selected_version
    start_date, end_date, date_source, _span = _page_date_range_or_version_span(
        engine,
        int(version or 0),
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = (
        engine.downtime_impact(int(version), start_date, end_date)
        if version is not None
        else {"version": None, "start_date": start_date, "end_date": end_date, "machines": []}
    )
    has_history = bool(versions)
    empty_reason = None
    if not rep.get("machines"):
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
        start_date=rep["start_date"],
        end_date=rep["end_date"],
        rows=rep["machines"],
        date_source=date_source,
        has_history=has_history,
        empty_reason=empty_reason,
    )


@bp.get("/downtime/export")
def downtime_export():
    start_raw = (request.args.get("start_date") or "").strip()
    end_raw = (request.args.get("end_date") or "").strip()
    if not start_raw or not end_raw:
        start_date, end_date = _default_date_range(days=7)
    else:
        start_date = _validate_ymd_date(start_raw, field="开始日期")
        end_date = _validate_ymd_date(end_raw, field="结束日期")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_downtime_impact_xlsx(version, start_date, end_date)
    return _send_report_export_file(x)
