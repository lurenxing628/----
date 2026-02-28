from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, url_for

from core.services.system import SystemConfigService
from core.services.system.operation_log_service import OperationLogService
from web.ui_mode import render_ui_template as render_template

from .pagination import paginate_rows, parse_page_args
from .system_bp import bp
from .system_utils import _get_job_state_map, _get_system_cfg_snapshot, _normalize_time_range, _safe_int


@bp.get("/logs")
def logs_page():
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    module = (request.args.get("module") or "").strip() or None
    action = (request.args.get("action") or "").strip() or None
    log_level = (request.args.get("log_level") or "").strip() or None
    page, per_page = parse_page_args(request, default_per_page=50, max_per_page=500)
    limit = _safe_int(request.args.get("limit"), field="limit", default=per_page, min_v=1, max_v=500)

    start_norm, end_norm = _normalize_time_range(start_time, end_time)

    svc = OperationLogService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None))
    items = svc.list_recent(
        limit=limit,
        module=module,
        action=action,
        log_level=log_level,
        start_time=start_norm,
        end_time=end_norm,
    )

    view_rows = []
    for it in items:
        d = it.to_dict()
        detail_raw = d.get("detail")
        detail_obj: Optional[Dict[str, Any]] = None
        if detail_raw:
            try:
                parsed = json.loads(detail_raw)
                if isinstance(parsed, dict):
                    detail_obj = parsed
            except Exception:
                detail_obj = None
        d["detail_obj"] = detail_obj
        view_rows.append(d)

    # 语义约定：
    # - limit：总查询上限（仅在最近 N 条记录内分页）
    # - per_page：每页展示条数
    view_rows, pager = paginate_rows(view_rows, page, per_page)

    from core.services.system import SystemMaintenanceService

    return render_template(
        "system/logs.html",
        title="系统管理 - 操作日志",
        rows=view_rows,
        settings=_get_system_cfg_snapshot().to_dict(),
        job_state=_get_job_state_map(),
        maintenance_limits={
            "max_log_delete_per_run": int(SystemMaintenanceService.MAX_LOG_DELETE_PER_RUN),
            "min_keep_logs": int(SystemMaintenanceService.MIN_KEEP_LOGS),
        },
        filters={
            "start_time": start_time or "",
            "end_time": end_time or "",
            "module": module or "",
            "action": action or "",
            "log_level": log_level or "",
            "limit": str(limit),
        },
        pager=pager,
    )


@bp.post("/logs/settings")
def logs_settings():
    svc = SystemConfigService(g.db, logger=current_app.logger)
    svc.update_logs_settings(
        auto_log_cleanup_enabled=request.form.get("auto_log_cleanup_enabled"),
        auto_log_cleanup_keep_days=request.form.get("auto_log_cleanup_keep_days"),
        auto_log_cleanup_interval_minutes=request.form.get("auto_log_cleanup_interval_minutes"),
    )
    flash("日志自动清理设置已保存。", "success")
    return redirect(url_for("system.logs_page"))


@bp.post("/logs/delete")
def logs_delete():
    raw = (request.form.get("log_id") or "").strip()
    if not raw:
        flash("缺少 log_id。", "error")
        return redirect(url_for("system.logs_page"))
    try:
        log_id = int(raw)
    except Exception:
        flash("log_id 不合法（期望正整数）。", "error")
        return redirect(url_for("system.logs_page"))
    if log_id <= 0 or log_id > 10**12:
        flash("log_id 不合法（期望正整数）。", "error")
        return redirect(url_for("system.logs_page"))

    deleted = OperationLogService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None)).delete_by_id(
        int(log_id)
    )

    if deleted <= 0:
        flash(f"未找到日志：ID={log_id}", "warning")
        return redirect(url_for("system.logs_page"))

    flash(f"已删除日志：ID={log_id}", "success")
    return redirect(url_for("system.logs_page"))


@bp.post("/logs/delete-batch")
def logs_delete_batch():
    raw_ids = request.form.getlist("log_ids")
    if not raw_ids:
        flash("请至少选择 1 条日志。", "error")
        return redirect(url_for("system.logs_page"))

    ids: List[int] = []
    for x in raw_ids:
        try:
            ids.append(int(str(x).strip()))
        except Exception:
            continue
    ids = [x for x in ids if x > 0]
    if not ids:
        flash("选择的日志 ID 不合法。", "error")
        return redirect(url_for("system.logs_page"))

    deleted = OperationLogService(g.db, logger=current_app.logger, op_logger=getattr(g, "op_logger", None)).delete_by_ids(ids)

    flash(f"批量删除完成：成功 {deleted}。", "success" if deleted else "warning")
    return redirect(url_for("system.logs_page"))

