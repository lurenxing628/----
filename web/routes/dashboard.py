import json
from flask import Blueprint, g

from data.repositories.batch_repo import BatchRepository
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from web.ui_mode import render_ui_template as render_template


bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    batch_repo = BatchRepository(g.db)
    history_repo = ScheduleHistoryRepository(g.db)

    pending_count = len(batch_repo.list(status="pending"))
    scheduled_count = len(batch_repo.list(status="scheduled"))
    overdue_count = 0

    recent = history_repo.list_recent(limit=1)
    latest = recent[0] if recent else None
    latest_summary = None
    if latest and latest.result_summary:
        try:
            latest_summary = (
                json.loads(latest.result_summary)
                if isinstance(latest.result_summary, str)
                else latest.result_summary
            )
        except Exception:
            latest_summary = None

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

