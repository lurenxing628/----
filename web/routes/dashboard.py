from __future__ import annotations

from flask import Blueprint, g

from web.ui_mode import render_ui_template as render_template

from .normalizers import _parse_result_summary_payload

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    services = g.services
    batch_svc = services.batch_service
    history_q = services.schedule_history_query_service

    pending_count = len(batch_svc.list(status="pending"))
    scheduled_count = len(batch_svc.list(status="scheduled"))
    overdue_count = 0

    recent = history_q.list_recent(limit=1)
    latest = recent[0] if recent else None
    latest_summary = None
    if latest and latest.result_summary:
        latest_summary = _parse_result_summary_payload(
            latest.result_summary, version=getattr(latest, "version", None), log_label="首页"
        )

    if isinstance(latest_summary, dict):
        overdue_payload = latest_summary.get("overdue_batches", {})
        if isinstance(overdue_payload, dict):
            raw_count = overdue_payload.get("count", 0)
            try:
                overdue_count = int(raw_count or 0)
            except (TypeError, ValueError):
                overdue_count = 0
        elif isinstance(overdue_payload, list):
            overdue_count = len(overdue_payload)

    return render_template(
        "dashboard.html",
        title="首页",
        pending_count=pending_count,
        scheduled_count=scheduled_count,
        overdue_count=overdue_count,
        latest_history=latest,
        latest_summary=latest_summary,
    )
