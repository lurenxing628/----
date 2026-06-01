from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from flask import Blueprint, current_app, g

from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.scheduler.execution_fact_provider import ExecutionFactProvider
from web.routes.history_summary_logging import log_history_summary_parse_warning
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.dashboard_workbench import build_dashboard_workbench_summary
from web.viewmodels.scheduler_history_summary import parse_history_summary_state

bp = Blueprint("dashboard", __name__)


def _positive_version(value: Any) -> int:
    try:
        version = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return version if version > 0 else 0


def _today_range(now: datetime) -> Dict[str, str]:
    start = datetime(now.year, now.month, now.day)
    end = start + timedelta(days=1)
    return {
        "start": start.strftime("%Y-%m-%d %H:%M:%S"),
        "end": end.strftime("%Y-%m-%d %H:%M:%S"),
    }


def _row_op_ids(rows: List[Dict[str, Any]]) -> List[int]:
    out: List[int] = []
    seen = set()
    for row in rows:
        try:
            op_id = int(row.get("op_id") or 0)
        except (TypeError, ValueError):
            continue
        if op_id <= 0 or op_id in seen:
            continue
        seen.add(op_id)
        out.append(op_id)
    return out


def _load_plan_time_span(services: Any, version: int):
    if version <= 0:
        return None
    try:
        return services.schedule_plan_query_service.get_plan_time_span(version, ROLE_ADOPTED)
    except Exception as exc:  # pragma: no cover - 防止首页被坏历史阻断
        current_app.logger.warning("首页值班台读取计划日期范围失败（version=%s）：%s", version, exc)
        return None


def _load_today_rows(services: Any, version: int, now: datetime) -> List[Dict[str, Any]]:
    if version <= 0:
        return []
    dr = _today_range(now)
    try:
        rows = services.schedule_plan_query_service.list_plan_detail_rows_between(
            version=version,
            role=ROLE_ADOPTED,
            start_time=dr["start"],
            end_time=dr["end"],
        )
    except Exception as exc:  # pragma: no cover - 防止首页被坏历史阻断
        current_app.logger.warning("首页值班台读取今日计划失败（version=%s）：%s", version, exc)
        return []
    return [dict(row) for row in rows]


def _load_execution_facts(rows: List[Dict[str, Any]]) -> Tuple[Dict[int, Any], str]:
    op_ids = _row_op_ids(rows)
    if not op_ids:
        return {}, ""
    try:
        return ExecutionFactProvider(g.db, logger=current_app.logger).facts_by_op_id(op_ids), ""
    except Exception as exc:  # pragma: no cover - 防止首页被坏现场记录阻断
        current_app.logger.warning("首页值班台读取现场情况失败：%s", exc)
        return {}, "现场执行事实读取失败，首页暂时不能判断哪些任务现场情况待确认。"


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

    now = datetime.now()
    latest_version = _positive_version(getattr(latest, "version", None) if latest is not None else None)
    plan_time_span = _load_plan_time_span(services, latest_version)
    today_rows = _load_today_rows(services, latest_version, now)
    execution_facts_by_op_id, execution_facts_load_error = _load_execution_facts(today_rows)
    workbench_summary = build_dashboard_workbench_summary(
        pending_count=pending_count,
        scheduled_count=scheduled_count,
        overdue_count=overdue_count,
        latest_history=latest,
        latest_summary=latest_summary,
        latest_summary_parse_state=latest_summary_parse_state,
        plan_time_span=plan_time_span,
        today_rows=today_rows,
        execution_facts_by_op_id=execution_facts_by_op_id,
        execution_facts_load_error=execution_facts_load_error,
        now=now,
    )

    return render_template(
        "dashboard.html",
        title="首页",
        pending_count=pending_count,
        scheduled_count=scheduled_count,
        overdue_count=overdue_count,
        latest_history=latest,
        latest_summary=latest_summary,
        workbench_summary=workbench_summary,
    )
