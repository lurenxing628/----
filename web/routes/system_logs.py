from __future__ import annotations

from typing import Any, Dict, List, Optional

from flask import flash, redirect, render_template, request, url_for

from core.infrastructure.errors import AppError
from web.routes.form_values import form_yes_no_value
from web.viewmodels.system_logs_vm import (
    build_operation_log_view_rows,
    build_system_logs_page_view_model,
    resolve_operation_log_action_filter,
    resolve_operation_log_module_filter,
)

from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import (
    _get_job_state_map,
    _get_operation_log_service,
    _get_system_cfg_snapshot,
    _get_system_config_service,
    _normalize_time_range,
    _safe_int,
)

_MAX_OPERATION_LOG_ID = 10**12


@bp.get("/logs")
def logs_page():
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    module_raw = (request.args.get("module") or "").strip()
    action_raw = (request.args.get("action") or "").strip()
    module = resolve_operation_log_module_filter(module_raw) or None
    action = resolve_operation_log_action_filter(action_raw) or None
    log_level = (request.args.get("log_level") or "").strip() or None
    page, per_page = parse_page_args(request, default_per_page=50, max_per_page=500)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=500)

    start_norm, end_norm = _normalize_time_range(start_time, end_time)

    svc = _get_operation_log_service()
    items = svc.list_recent(
        limit=limit,
        module=module,
        action=action,
        log_level=log_level,
        start_time=start_norm,
        end_time=end_norm,
    )

    view_rows = build_operation_log_view_rows(items)

    # 语义约定：
    # - limit：总查询上限（仅在最近 N 条记录内分页）
    # - per_page：每页展示条数
    view_rows, pager = paginate_rows(view_rows, page, per_page)

    from core.services.system import SystemMaintenanceService

    settings = _get_system_cfg_snapshot().to_dict()

    return render_template(
        "system/logs.html",
        title="系统管理 - 操作日志",
        rows=view_rows,
        settings=settings,
        page=build_system_logs_page_view_model(settings),
        job_state=_get_job_state_map(),
        maintenance_limits={
            "max_log_delete_per_run": int(SystemMaintenanceService.MAX_LOG_DELETE_PER_RUN),
            "min_keep_logs": int(SystemMaintenanceService.MIN_KEEP_LOGS),
        },
        filters={
            "start_time": start_time or "",
            "end_time": end_time or "",
            "module": module_raw,
            "module_code": module or "",
            "action": action_raw,
            "action_code": action or "",
            "log_level": log_level or "",
            "limit": str(limit),
        },
        pager=pager,
    )


@bp.post("/logs/settings")
def logs_settings():
    try:
        svc = _get_system_config_service()
        svc.update_logs_settings(
            auto_log_cleanup_enabled=form_yes_no_value(request.form, "auto_log_cleanup_enabled"),
            auto_log_cleanup_keep_days=request.form.get("auto_log_cleanup_keep_days"),
            auto_log_cleanup_interval_minutes=request.form.get("auto_log_cleanup_interval_minutes"),
        )
        flash("日志自动清理设置已保存。", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("system.logs_page"))


@bp.post("/logs/delete")
def logs_delete():
    try:
        log_id = _parse_log_id(request.form.get("log_id"))
    except ValueError:
        flash("日志编号不合法，请填写正整数。", "error")
        return redirect(url_for("system.logs_page"))

    svc = _get_operation_log_service()
    deleted = svc.delete_by_id(int(log_id))

    if deleted <= 0:
        flash(f"未找到日志：编号 {log_id}", "warning")
        return redirect(url_for("system.logs_page"))

    flash(f"已删除日志：编号 {log_id}", "success")
    return redirect(url_for("system.logs_page"))


@bp.post("/logs/delete-batch")
def logs_delete_batch():
    raw_ids = request.form.getlist("log_ids")
    if not raw_ids:
        flash("请至少选择 1 条日志。", "error")
        return redirect(url_for("system.logs_page"))

    ids: List[int] = []
    invalid_ids: List[str] = []
    for raw in raw_ids:
        try:
            ids.append(_parse_log_id(raw))
        except ValueError:
            invalid_ids.append(_display_log_id(raw))

    if invalid_ids:
        flash("选择的日志编号不合法：" + "、".join(invalid_ids[:10]), "error")
        return redirect(url_for("system.logs_page"))

    svc = _get_operation_log_service()
    deleted = svc.delete_by_ids(ids)

    if deleted < len(ids):
        flash(
            f"批量删除完成：成功 {deleted}，有 {len(ids) - deleted} 条日志未找到或已被删除。",
            "warning",
        )
    else:
        flash(f"批量删除完成：成功 {deleted}。", "success" if deleted else "warning")
    return redirect(url_for("system.logs_page"))


def _display_log_id(raw: Any) -> str:
    return str(raw or "").strip() or "（空）"


def _parse_log_id(raw: Any) -> int:
    shown = _display_log_id(raw)
    try:
        log_id = int(shown)
    except (TypeError, ValueError) as exc:
        raise ValueError("日志编号不合法") from exc
    if log_id <= 0 or log_id > _MAX_OPERATION_LOG_ID:
        raise ValueError("日志编号不合法")
    return log_id
