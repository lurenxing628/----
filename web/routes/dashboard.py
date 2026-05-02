from __future__ import annotations

from flask import Blueprint, g

from web.routes.history_summary_logging import log_history_summary_parse_warning
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import parse_history_summary_state

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
    latest_summary_parse_state = parse_history_summary_state(
        getattr(latest, "result_summary", None) if latest is not None else None
    )
    log_history_summary_parse_warning(
        latest_summary_parse_state,
        version=getattr(latest, "version", None) if latest is not None else None,
        log_label="首页",
    )
    latest_payload = latest_summary_parse_state.get("payload")
    latest_summary = latest_payload if isinstance(latest_payload, dict) else None

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
