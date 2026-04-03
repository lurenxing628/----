from __future__ import annotations

from typing import Optional

from flask import g, request

from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService
from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, safe_int

from .normalizers import normalize_version_or_latest
from .scheduler_bp import bp


@bp.get("/analysis")
def analysis_page():
    """
    排产效果/优化分析：
    - 展示 result_summary.algo 中的指标、尝试列表（attempts），以及最近版本趋势。
    - 不依赖外网与第三方图表库（Win7 离线可用）。
    """
    q = ScheduleHistoryQueryService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    versions = q.list_versions(limit=50)

    latest_version = safe_int((versions[0] or {}).get("version"), default=0) if versions else 0
    selected_ver: Optional[int] = None
    if "version" in request.args:
        selected_ver = normalize_version_or_latest(request.args.get("version"), latest_version=latest_version) or None
    else:
        if versions:
            selected_ver = safe_int((versions[0] or {}).get("version"), default=0) or None

    raw_hist = q.list_recent(limit=400)
    selected_item = q.get_by_version(int(selected_ver)) if selected_ver is not None else None
    ctx = build_analysis_context(selected_ver=selected_ver, raw_hist=raw_hist, selected_item=selected_item)

    return render_template(
        "scheduler/analysis.html",
        title="排产优化分析",
        versions=versions,
        **ctx,
    )

