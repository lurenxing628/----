from __future__ import annotations

import json
from typing import Any, Optional

from flask import current_app, g, request

from core.infrastructure.errors import ValidationError
from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import _safe_int


def _parse_result_summary(raw_summary: Any, *, version: Any, source: str) -> Optional[Any]:
    try:
        parsed = json.loads(raw_summary or "{}")
    except Exception as exc:
        current_app.logger.warning(
            "排产历史页 result_summary 解析失败（version=%s, source=%s, error=%s）",
            version,
            source,
            exc.__class__.__name__,
        )
        return None
    return parsed if isinstance(parsed, dict) else parsed


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    page, per_page = parse_page_args(request, default_per_page=20, max_per_page=200)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=200)

    q = ScheduleHistoryQueryService(g.db, logger=getattr(g, "app_logger", None), op_logger=getattr(g, "op_logger", None))
    versions = q.list_versions(limit=30)

    selected = None
    selected_summary = None
    if version_raw:
        try:
            ver = int(version_raw)
        except Exception as e:
            raise ValidationError("version 不合法（期望整数）", field="version") from e
        item = q.get_by_version(ver)
        if item:
            selected = item.to_dict()
            if selected.get("result_summary"):
                selected_summary = _parse_result_summary(
                    selected.get("result_summary"),
                    version=ver,
                    source="selected",
                )

    items = [x.to_dict() for x in q.list_recent(limit=limit)]
    for it in items:
        if it.get("result_summary"):
            it["result_summary_obj"] = _parse_result_summary(
                it.get("result_summary"),
                version=it.get("version"),
                source="list",
            )
    # 语义约定：
    # - limit：总查询上限（仅在最近 N 条记录内分页）
    # - per_page：每页展示条数
    items, pager = paginate_rows(items, page, per_page)

    return render_template(
        "system/history.html",
        title="系统管理 - 排产历史",
        versions=versions,
        selected=selected,
        selected_summary=selected_summary,
        items=items,
        filters={"version": version_raw, "limit": str(limit)},
        pager=pager,
    )
