from __future__ import annotations

from flask import request

from web.ui_mode import render_ui_template as render_template
from web.viewmodels.scheduler_history_summary import decorate_history_version_options
from web.viewmodels.scheduler_summary_display import build_summary_display_state

from .domains.scheduler.scheduler_history_resolution import build_requested_history_resolution
from .normalizers import (
    _parse_result_summary_payload_with_meta,
    parse_optional_version_int,
)
from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import _get_schedule_history_query_service, _safe_int


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    page, per_page = parse_page_args(request, default_per_page=20, max_per_page=200)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=200)

    q = _get_schedule_history_query_service()
    versions = decorate_history_version_options(q.list_versions(limit=30))

    selected = None
    selected_missing_message = None
    selected_missing_version = None
    selected_summary = None
    selected_summary_display = build_summary_display_state(None, result_status=None)
    ver = parse_optional_version_int(request.args.get("version"), field="version")
    if ver is not None:
        item = q.get_by_version(ver)
        if item:
            selected = item.to_dict()
            parse_state = _parse_result_summary_payload_with_meta(
                selected.get("result_summary"),
                version=ver,
                source="selected",
                log_label="排产历史页",
            )
            selected_summary = parse_state.get("payload")
            selected_summary_display = build_summary_display_state(
                selected_summary if isinstance(selected_summary, dict) else None,
                result_status=selected.get("result_status"),
                parse_state=parse_state,
            )
        else:
            selected_missing_version = int(ver)
            selected_missing_message = f"v{int(ver)} 无对应排产历史"

    items = [x.to_dict() for x in q.list_recent(limit=limit)]
    for it in items:
        parse_state = _parse_result_summary_payload_with_meta(
            it.get("result_summary"),
            version=it.get("version"),
            source="list",
            log_label="排产历史页",
        )
        summary_payload = parse_state.get("payload")
        if summary_payload is not None:
            it["result_summary_obj"] = summary_payload
        it["result_summary_display"] = build_summary_display_state(
            summary_payload if isinstance(summary_payload, dict) else None,
            result_status=it.get("result_status"),
            parse_state=parse_state,
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
        selected_summary_display=selected_summary_display,
        selected_history_resolution=build_requested_history_resolution(
            requested_version=selected_missing_version,
            selected_history=selected,
            missing_message=selected_missing_message,
        ),
        selected_missing_version=selected_missing_version,
        selected_missing_message=selected_missing_message,
        items=items,
        filters={"version": version_raw, "limit": str(limit)},
        pager=pager,
    )
