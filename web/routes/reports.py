from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, g, request, send_file

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import ValidationError
from core.services.report import ReportEngine


bp = Blueprint("reports", __name__)


def _default_date_range(days: int = 7):
    end_d = date.today()
    start_d = end_d - timedelta(days=max(0, int(days) - 1))
    return start_d.isoformat(), end_d.isoformat()


def _validate_ymd_date(raw: str, field: str) -> str:
    s = (raw or "").strip()
    if not s:
        raise ValidationError("缺少 start_date/end_date", field="date_range")

    s = s.replace("/", "-")
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        raise ValidationError("日期格式不正确（允许：YYYY-MM-DD / YYYY/MM/DD）", field=field)
    return s


def _export_version_or_latest(engine: ReportEngine) -> int:
    """
    导出接口的 version 解析规则：
    - version 缺失/空字符串/无法转 int/<=0：回落到最新版本（与页面默认口径一致）
    - 若无排产历史，latest_version() 可能为 0（保持现状）
    """
    latest = int(engine.latest_version() or 0)
    raw = request.args.get("version")
    if raw is None:
        return latest
    s = str(raw).strip()
    if s == "":
        return latest
    try:
        v = int(s)
    except Exception:
        return latest
    if v <= 0:
        return latest
    return v


def _page_version_or_latest(engine: ReportEngine) -> int:
    latest = int(engine.latest_version() or 0)
    raw = request.args.get("version")
    if raw is None:
        return latest
    s = str(raw).strip()
    if s == "":
        return latest
    try:
        return int(s)
    except Exception:
        return latest


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


@bp.get("/")
def index():
    return render_template("reports/index.html", title="报表中心")


@bp.get("/overdue")
def overdue_page():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=30)
    version = _page_version_or_latest(engine)
    rep = engine.overdue_batches(version)
    has_history = bool(versions)
    empty_reason = None
    if int(rep.get("count") or 0) <= 0:
        empty_reason = "no_history" if not has_history else "no_overdue"
    return render_template(
        "reports/overdue.html",
        title="报表 - 超期清单",
        versions=versions,
        version=int(rep["version"]),
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
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)


@bp.get("/utilization")
def utilization_page():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=30)
    version = _page_version_or_latest(engine)
    start_date, end_date, date_source, _span = _page_date_range_or_version_span(
        engine,
        version,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = engine.utilization(version, start_date, end_date)
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
        version=int(rep["version"]),
        start_date=rep["start_date"],
        end_date=rep["end_date"],
        capacity_hours=rep["capacity_hours_per_resource"],
        machine_rows=rep["machines"],
        operator_rows=rep["operators"],
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
        start_date = _validate_ymd_date(start_raw, field="start_date")
        end_date = _validate_ymd_date(end_raw, field="end_date")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_utilization_xlsx(version, start_date, end_date)
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)


@bp.get("/downtime")
def downtime_page():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=30)
    version = _page_version_or_latest(engine)
    start_date, end_date, date_source, _span = _page_date_range_or_version_span(
        engine,
        version,
        request.args.get("start_date") or "",
        request.args.get("end_date") or "",
    )

    rep = engine.downtime_impact(version, start_date, end_date)
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
        version=int(rep["version"]),
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
        start_date = _validate_ymd_date(start_raw, field="start_date")
        end_date = _validate_ymd_date(end_raw, field="end_date")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_downtime_impact_xlsx(version, start_date, end_date)
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)

