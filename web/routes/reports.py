from __future__ import annotations

from flask import Blueprint, g, render_template

from core.services.report import ReportEngine
from web.routes.reports_execution_review_page import execution_review_page_context
from web.routes.reports_export_routes import register_report_export_routes
from web.routes.reports_page_support import (
    downtime_page_context,
    overdue_page_context,
    reports_index_context,
    utilization_page_context,
)

bp = Blueprint("reports", __name__)
register_report_export_routes(bp)


@bp.get("/")
def index():
    return render_template("reports/index.html", **reports_index_context(ReportEngine(g.db), g.services))


@bp.get("/overdue")
def overdue_page():
    return render_template("reports/overdue.html", **overdue_page_context(ReportEngine(g.db), g.services))


@bp.get("/utilization")
def utilization_page():
    return render_template("reports/utilization.html", **utilization_page_context(ReportEngine(g.db), g.services))


@bp.get("/execution-review")
def execution_review_page():
    return render_template("reports/execution_review.html", **execution_review_page_context(ReportEngine(g.db), g.services))


@bp.get("/downtime")
def downtime_page():
    return render_template("reports/downtime.html", **downtime_page_context(ReportEngine(g.db), g.services))
