from __future__ import annotations

from flask import render_template, request

from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.viewmodels.scheduler_history_summary import decorate_history_version_options, parse_history_summary_state
from web.viewmodels.scheduler_summary_display import build_summary_display_state
from web.viewmodels.system_history_links import build_history_version_links

from .domains.scheduler.scheduler_history_resolution import build_requested_history_resolution
from .normalizers import (
    parse_optional_version_int,
)
from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import _get_request_service, _get_schedule_history_query_service, _safe_int

_SPAN_LOAD_ERROR_TEXT = "这条历史的计划日期范围读取失败，甘特、周计划和资源排班暂时不能从这里跳转。"


def _load_history_span_dates(plan_query_service, version, span_cache):
    """取该版本 adopted 计划的日期跨度，结果按 version 缓存（selected 与列表行常重合）。

    宽 catch：resolve_plan_view 会因缺 adopted/未知角色等数据问题抛 ValueError，
    同属「该行数据坏」语义（dashboard _load_plan_time_span 先例）——错误文案
    进链接 context 变成该行禁用原因，单行坏历史不炸整页。
    """
    from core.services.scheduler.schedule_result_view_range import get_plan_time_span_dates

    try:
        version_int = int(version)
    except (TypeError, ValueError):
        return None, ""
    if version_int <= 0:
        return None, ""
    if version_int in span_cache:
        return span_cache[version_int]
    try:
        result = (get_plan_time_span_dates(plan_query_service, version_int, "adopted", None), "")
    except Exception:
        result = (None, _SPAN_LOAD_ERROR_TEXT)
    span_cache[version_int] = result
    return result


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    page, per_page = parse_page_args(request, default_per_page=20, max_per_page=200)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=200)

    q = _get_schedule_history_query_service()
    versions = decorate_history_version_options(q.list_versions(limit=30))
    log_history_version_option_parse_warnings(versions, log_label="排产历史页")

    selected = None
    selected_missing_message = None
    selected_missing_version = None
    selected_summary = None
    selected_summary_display = build_summary_display_state(None, result_status=None)
    ver = parse_optional_version_int(request.args.get("version"), field="version")
    if ver is not None:
        item = q.get_by_version(ver)
        if item:
            selected = decorate_history_version_options([item.to_dict()])[0]
            parse_state = parse_history_summary_state(selected.get("result_summary"))
            log_history_summary_parse_warning(
                parse_state,
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

    items = decorate_history_version_options([x.to_dict() for x in q.list_recent(limit=limit)])
    for it in items:
        parse_state = parse_history_summary_state(it.get("result_summary"))
        log_history_summary_parse_warning(
            parse_state,
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

    # 先分页后装配行级工作台链接：span 查询上界 = 当前页行 + selected（≤per_page+1），
    # 同版本走 span_cache 去重（fusion-handrolled-links-adoption）
    plan_query_service = _get_request_service("schedule_plan_query_service")
    span_cache: dict = {}
    for it in items:
        span, span_error = _load_history_span_dates(plan_query_service, it.get("version"), span_cache)
        it["workbench_links"] = build_history_version_links(it.get("version"), span=span, span_error=span_error)
    selected_workbench_links = []
    if selected:
        span, span_error = _load_history_span_dates(plan_query_service, selected.get("version"), span_cache)
        selected_workbench_links = build_history_version_links(
            selected.get("version"), span=span, span_error=span_error
        )

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
        selected_workbench_links=selected_workbench_links,
        items=items,
        filters={"version": version_raw, "limit": str(limit)},
        pager=pager,
    )
