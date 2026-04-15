from __future__ import annotations

from flask import request

from core.infrastructure.errors import ValidationError
from web.ui_mode import render_ui_template as render_template

from .normalizers import _parse_result_summary_payload
from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import _get_schedule_history_query_service, _safe_int


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    page, per_page = parse_page_args(request, default_per_page=20, max_per_page=200)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=200)

    q = _get_schedule_history_query_service()
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
                selected_summary = _parse_result_summary_payload(
                    selected.get("result_summary"),
                    version=ver,
                    source="selected",
                    log_label="排产历史页",
                )

    items = [x.to_dict() for x in q.list_recent(limit=limit)]
    for it in items:
        if it.get("result_summary"):
            it["result_summary_obj"] = _parse_result_summary_payload(
                it.get("result_summary"),
                version=it.get("version"),
                source="list",
                log_label="排产历史页",
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
