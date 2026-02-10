from __future__ import annotations

from datetime import date, datetime, timedelta

from flask import Blueprint, flash, g, redirect, request, send_file, url_for

from web.ui_mode import render_ui_template as render_template

from core.infrastructure.errors import AppError, ValidationError
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


@bp.get("/")
def index():
    return render_template("reports/index.html", title="报表中心")


@bp.get("/overdue")
def overdue_page():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=30)
    latest = engine.latest_version()
    v = request.args.get("version")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else int(latest)
    except Exception:
        version = int(latest)
    rep = engine.overdue_batches(version)
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
    latest = engine.latest_version()

    v = request.args.get("version")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else int(latest)
    except Exception:
        version = int(latest)

    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    if not start_date or not end_date:
        start_date, end_date = _default_date_range(days=7)

    rep = engine.utilization(version, start_date, end_date)
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
    )


@bp.get("/utilization/export")
def utilization_export():
    start_date = _validate_ymd_date(request.args.get("start_date"), field="start_date")
    end_date = _validate_ymd_date(request.args.get("end_date"), field="end_date")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_utilization_xlsx(version, start_date, end_date)
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)


@bp.get("/downtime")
def downtime_page():
    engine = ReportEngine(g.db)
    versions = engine.list_versions(limit=30)
    latest = engine.latest_version()

    v = request.args.get("version")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else int(latest)
    except Exception:
        version = int(latest)

    start_date = (request.args.get("start_date") or "").strip() or None
    end_date = (request.args.get("end_date") or "").strip() or None
    if not start_date or not end_date:
        start_date, end_date = _default_date_range(days=7)

    rep = engine.downtime_impact(version, start_date, end_date)
    return render_template(
        "reports/downtime.html",
        title="报表 - 停机影响统计",
        versions=versions,
        version=int(rep["version"]),
        start_date=rep["start_date"],
        end_date=rep["end_date"],
        rows=rep["machines"],
    )


@bp.get("/downtime/export")
def downtime_export():
    start_date = _validate_ymd_date(request.args.get("start_date"), field="start_date")
    end_date = _validate_ymd_date(request.args.get("end_date"), field="end_date")
    engine = ReportEngine(g.db)
    version = _export_version_or_latest(engine)
    x = engine.export_downtime_impact_xlsx(version, start_date, end_date)
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)

