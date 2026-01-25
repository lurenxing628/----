from __future__ import annotations

from datetime import date, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, send_file, url_for

from core.infrastructure.errors import AppError, ValidationError
from core.services.report import ReportEngine


bp = Blueprint("reports", __name__)


def _default_date_range(days: int = 7):
    end_d = date.today()
    start_d = end_d - timedelta(days=max(0, int(days) - 1))
    return start_d.isoformat(), end_d.isoformat()


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
    )


@bp.get("/overdue/export")
def overdue_export():
    v = request.args.get("version")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else 0
    except Exception:
        version = 0
    engine = ReportEngine(g.db)
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
    v = request.args.get("version")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        raise ValidationError("缺少 start_date/end_date", field="date_range")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else 0
    except Exception:
        version = 0
    engine = ReportEngine(g.db)
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
    v = request.args.get("version")
    start_date = request.args.get("start_date")
    end_date = request.args.get("end_date")
    if not start_date or not end_date:
        raise ValidationError("缺少 start_date/end_date", field="date_range")
    try:
        version = int(v) if v is not None and str(v).strip() != "" else 0
    except Exception:
        version = 0
    engine = ReportEngine(g.db)
    x = engine.export_downtime_impact_xlsx(version, start_date, end_date)
    return send_file(x.data, as_attachment=True, download_name=x.filename, mimetype=x.content_type)

