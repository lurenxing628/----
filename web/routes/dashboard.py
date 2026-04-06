from __future__ import annotations

import json

from flask import Blueprint, current_app, g

from core.services.scheduler import BatchService
from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService
from web.ui_mode import render_ui_template as render_template

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    batch_svc = BatchService(g.db, op_logger=getattr(g, "op_logger", None))
    history_q = ScheduleHistoryQueryService(
        g.db,
        logger=getattr(g, "app_logger", None),
        op_logger=getattr(g, "op_logger", None),
    )

    pending_count = len(batch_svc.list(status="pending"))
    scheduled_count = len(batch_svc.list(status="scheduled"))
    overdue_count = 0

    recent = history_q.list_recent(limit=1)
    latest = recent[0] if recent else None
    latest_summary = None
    if latest and latest.result_summary:
        try:
            latest_summary = (
                json.loads(latest.result_summary)
                if isinstance(latest.result_summary, str)
                else latest.result_summary
            )
        except Exception as exc:
            current_app.logger.warning(
                "首页 result_summary 解析失败（version=%s, error=%s）",
                getattr(latest, "version", None),
                exc.__class__.__name__,
            )
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
