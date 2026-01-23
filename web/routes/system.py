from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from flask import Blueprint, current_app, flash, g, redirect, render_template, request, url_for

from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema
from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.infrastructure.logging import OperationLogger
from core.services.system import SystemConfigService
from data.repositories import OperationLogRepository, ScheduleHistoryRepository, SystemJobStateRepository


bp = Blueprint("system", __name__)


def _parse_dt(value: str, field: str) -> Tuple[datetime, bool]:
    """
    解析时间参数：
    - 支持 YYYY-MM-DD
    - 支持 YYYY-MM-DD HH:MM:SS
    返回：(dt, is_date_only)
    """
    v = (value or "").strip()
    if not v:
        raise ValidationError("时间不能为空", field=field)

    try:
        if len(v) == 10:
            return datetime.strptime(v, "%Y-%m-%d"), True
        return datetime.strptime(v, "%Y-%m-%d %H:%M:%S"), False
    except Exception:
        raise ValidationError("时间格式不正确（允许：YYYY-MM-DD 或 YYYY-MM-DD HH:MM:SS）", field=field)


def _normalize_time_range(start_raw: Optional[str], end_raw: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    """
    把查询参数标准化为 SQLite 兼容的字符串格式：
    - start：日期则取 00:00:00
    - end：日期则取 23:59:59
    """
    start_s = (start_raw or "").strip() or None
    end_s = (end_raw or "").strip() or None

    start_norm = None
    end_norm = None

    if start_s:
        dt, is_date_only = _parse_dt(start_s, field="start_time")
        if is_date_only:
            dt = dt.replace(hour=0, minute=0, second=0)
        start_norm = dt.strftime("%Y-%m-%d %H:%M:%S")

    if end_s:
        dt, is_date_only = _parse_dt(end_s, field="end_time")
        if is_date_only:
            dt = dt.replace(hour=23, minute=59, second=59)
        end_norm = dt.strftime("%Y-%m-%d %H:%M:%S")

    # 若两者都存在，校验 start <= end
    if start_norm and end_norm:
        try:
            if datetime.strptime(start_norm, "%Y-%m-%d %H:%M:%S") > datetime.strptime(end_norm, "%Y-%m-%d %H:%M:%S"):
                raise ValidationError("开始时间不能晚于结束时间。", field="start_time")
        except ValidationError:
            raise
        except Exception:
            pass

    return start_norm, end_norm


def _safe_int(value: Optional[str], field: str, default: int, min_v: int, max_v: int) -> int:
    raw = (value or "").strip()
    if raw == "":
        return int(default)
    try:
        v = int(raw)
    except Exception:
        raise ValidationError(f"{field} 不合法（期望整数）", field=field)
    if v < min_v:
        return int(min_v)
    if v > max_v:
        return int(max_v)
    return v


def _get_backup_manager(keep_days: Optional[int] = None) -> BackupManager:
    return BackupManager(
        db_path=current_app.config["DATABASE_PATH"],
        backup_dir=current_app.config["BACKUP_DIR"],
        keep_days=int(keep_days) if keep_days is not None else int(current_app.config.get("BACKUP_KEEP_DAYS", 7)),
        logger=current_app.logger,
    )

def _get_system_cfg_snapshot():
    svc = SystemConfigService(g.db, logger=current_app.logger)
    return svc.get_snapshot(backup_keep_days_default=int(current_app.config.get("BACKUP_KEEP_DAYS", 7)))


def _get_job_state_map() -> Dict[str, Any]:
    repo = SystemJobStateRepository(g.db)
    def _get(key: str) -> Optional[Dict[str, Any]]:
        it = repo.get(key)
        return it.to_dict() if it else None

    return {
        "auto_backup": _get("auto_backup"),
        "auto_backup_cleanup": _get("auto_backup_cleanup"),
        "auto_log_cleanup": _get("auto_log_cleanup"),
    }



def _validate_backup_filename(filename: str) -> str:
    fn = (filename or "").strip()
    if not fn:
        raise ValidationError("请选择要恢复的备份文件。", field="filename")

    base = os.path.basename(fn)
    if base != fn:
        raise ValidationError("备份文件名不合法。", field="filename")

    if not base.startswith("aps_backup_") or not base.endswith(".db"):
        raise ValidationError("备份文件名不合法（仅允许 aps_backup_*.db）。", field="filename")

    return base


@bp.get("/")
def index():
    return redirect(url_for("system.backup_page"))


@bp.get("/backup")
def backup_page():
    cfg = _get_system_cfg_snapshot()
    keep_days = int(cfg.auto_backup_keep_days)
    mgr = _get_backup_manager(keep_days=keep_days)
    backups = mgr.list_backups()
    return render_template(
        "system/backup.html",
        title="系统管理 - 备份/恢复",
        backups=backups,
        keep_days=keep_days,
        settings=cfg.to_dict(),
        job_state=_get_job_state_map(),
    )


@bp.post("/backup/create")
def backup_create():
    cfg = _get_system_cfg_snapshot()
    mgr = _get_backup_manager(keep_days=int(cfg.auto_backup_keep_days))
    path = mgr.backup(suffix="manual")
    filename = os.path.basename(path)
    size_mb = None
    try:
        size_mb = round(os.stat(path).st_size / 1024 / 1024, 2)
    except Exception:
        size_mb = None

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="backup",
            target_type="backup",
            target_id=filename,
            detail={
                "filename": filename,
                "suffix": "manual",
                "size_mb": size_mb,
            },
        )

    flash(f"已创建备份：{filename}", "success")
    return redirect(url_for("system.backup_page"))

@bp.post("/backup/settings")
def backup_settings():
    """
    保存备份页的自动任务设置（按请求触发：自动备份/自动清理备份）。
    """
    svc = SystemConfigService(g.db, logger=current_app.logger)
    svc.update_backup_settings(
        auto_backup_enabled=request.form.get("auto_backup_enabled"),
        auto_backup_interval_minutes=request.form.get("auto_backup_interval_minutes"),
        auto_backup_cleanup_enabled=request.form.get("auto_backup_cleanup_enabled"),
        auto_backup_keep_days=request.form.get("auto_backup_keep_days"),
        auto_backup_cleanup_interval_minutes=request.form.get("auto_backup_cleanup_interval_minutes"),
    )
    flash("备份自动任务设置已保存。", "success")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/delete")
def backup_delete():
    filename = _validate_backup_filename(request.form.get("filename") or "")
    backup_dir = current_app.config["BACKUP_DIR"]
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.exists(backup_path):
        flash(f"备份文件不存在：{filename}", "error")
        return redirect(url_for("system.backup_page"))
    try:
        os.remove(backup_path)
        if getattr(g, "op_logger", None) is not None:
            g.op_logger.info(
                module="system",
                action="backup_delete",
                target_type="backup",
                target_id=filename,
                detail={"filename": filename, "mode": "manual"},
            )
        flash(f"已删除备份：{filename}", "success")
    except Exception as e:
        flash(f"删除失败：{e}", "error")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/delete-batch")
def backup_delete_batch():
    filenames = request.form.getlist("filenames")
    if not filenames:
        flash("请至少选择 1 个备份文件。", "error")
        return redirect(url_for("system.backup_page"))

    backup_dir = current_app.config["BACKUP_DIR"]
    ok = 0
    failed: List[str] = []
    deleted: List[str] = []
    for raw in filenames:
        try:
            fn = _validate_backup_filename(raw)
        except Exception:
            failed.append(str(raw))
            continue
        p = os.path.join(backup_dir, fn)
        if not os.path.exists(p):
            failed.append(fn)
            continue
        try:
            os.remove(p)
            ok += 1
            deleted.append(fn)
        except Exception:
            failed.append(fn)
            continue

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="backup_delete",
            target_type="backup",
            target_id=None,
            detail={
                "mode": "batch",
                "deleted_count": int(ok),
                "failed_count": int(len(failed)),
                "deleted_sample": deleted[:20],
                "failed_sample": failed[:20],
            },
        )

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "，".join(failed[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/cleanup")
def backup_cleanup():
    cfg = _get_system_cfg_snapshot()
    mgr = _get_backup_manager(keep_days=int(cfg.auto_backup_keep_days))
    before = mgr.list_backups()
    mgr.cleanup_old_backups()
    after = mgr.list_backups()
    removed = max(0, len(before) - len(after))

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="cleanup",
            target_type="backup",
            target_id=None,
            detail={"keep_days": int(mgr.keep_days), "removed_count": int(removed), "mode": "manual"},
        )

    flash(f"已清理过期备份：删除 {removed} 个（保留 {mgr.keep_days} 天内的备份）。", "success")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/restore")
def backup_restore():
    """
    恢复数据库：
    - 恢复前自动备份 before_restore（由 BackupManager.restore() 内部保证）
    - 为避免 sqlite 文件锁：先关闭本次请求的 g.db 连接
    - 恢复后确保 schema（避免恢复旧库缺表）
    - 恢复动作写 OperationLogs（使用独立连接，避免依赖已关闭的 g.db）
    """
    filename = _validate_backup_filename(request.form.get("filename") or "")
    backup_dir = current_app.config["BACKUP_DIR"]
    backup_path = os.path.join(backup_dir, filename)
    if not os.path.exists(backup_path):
        raise ValidationError(f"备份文件不存在：{filename}", field="filename")

    # 关闭本请求 DB（避免 restore 时被占用）
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass
    g.pop("op_logger", None)

    mgr = _get_backup_manager()
    ok = mgr.restore(backup_path)
    if not ok:
        raise AppError(ErrorCode.DB_QUERY_ERROR, "数据库恢复失败，请查看日志。")

    # 恢复后确保 schema（索引/新表）
    try:
        ensure_schema(current_app.config["DATABASE_PATH"], current_app.logger)
    except Exception as e:
        current_app.logger.warning(f"恢复后 ensure_schema 失败（不阻断）：{e}")

    # 写入操作日志（独立连接）
    try:
        conn = sqlite3.connect(current_app.config["DATABASE_PATH"])
        op_logger = OperationLogger(conn, logger=current_app.logger)
        op_logger.info(
            module="system",
            action="restore",
            target_type="backup",
            target_id=filename,
            detail={
                "filename": filename,
                "backup_dir": backup_dir,
                "note": "已恢复数据库；恢复前自动备份 before_restore 已执行。",
            },
        )
        try:
            conn.close()
        except Exception:
            pass
    except Exception as e:
        current_app.logger.error(f"恢复后写入操作日志失败：{e}")

    flash(f"已从备份恢复：{filename}。建议刷新页面/重新打开浏览器以加载最新数据。", "success")
    return redirect(url_for("system.backup_page"))


@bp.get("/logs")
def logs_page():
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    module = (request.args.get("module") or "").strip() or None
    action = (request.args.get("action") or "").strip() or None
    log_level = (request.args.get("log_level") or "").strip() or None
    limit = _safe_int(request.args.get("limit"), field="limit", default=50, min_v=1, max_v=500)

    start_norm, end_norm = _normalize_time_range(start_time, end_time)

    repo = OperationLogRepository(g.db)
    items = repo.list_recent(
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

    return render_template(
        "system/logs.html",
        title="系统管理 - 操作日志",
        rows=view_rows,
        settings=_get_system_cfg_snapshot().to_dict(),
        job_state=_get_job_state_map(),
        filters={
            "start_time": start_time or "",
            "end_time": end_time or "",
            "module": module or "",
            "action": action or "",
            "log_level": log_level or "",
            "limit": str(limit),
        },
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
    log_id = _safe_int(request.form.get("log_id"), field="log_id", default=0, min_v=1, max_v=10**12)
    repo = OperationLogRepository(g.db)
    deleted = repo.delete_by_id(int(log_id))
    if deleted <= 0:
        flash(f"未找到日志：ID={log_id}", "warning")
        return redirect(url_for("system.logs_page"))

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="logs_delete",
            target_type="operation_log",
            target_id=str(log_id),
            detail={"mode": "manual", "deleted_ids": [int(log_id)], "deleted_count": 1},
        )
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

    repo = OperationLogRepository(g.db)
    deleted = repo.delete_by_ids(ids)
    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="logs_delete",
            target_type="operation_log",
            target_id=None,
            detail={"mode": "batch", "deleted_count": int(deleted), "deleted_ids_sample": ids[:30]},
        )

    flash(f"批量删除完成：成功 {deleted}。", "success" if deleted else "warning")
    return redirect(url_for("system.logs_page"))


@bp.get("/history")
def history_page():
    version_raw = (request.args.get("version") or "").strip()
    limit = _safe_int(request.args.get("limit"), field="limit", default=20, min_v=1, max_v=200)

    repo = ScheduleHistoryRepository(g.db)
    versions = repo.list_versions(limit=30)

    selected = None
    selected_summary = None
    if version_raw:
        try:
            ver = int(version_raw)
        except Exception:
            raise ValidationError("version 不合法（期望整数）", field="version")
        item = repo.get_by_version(ver)
        if item:
            selected = item.to_dict()
            if selected.get("result_summary"):
                try:
                    selected_summary = json.loads(selected.get("result_summary") or "{}")
                except Exception:
                    selected_summary = None

    items = [x.to_dict() for x in repo.list_recent(limit=limit)]
    for it in items:
        if it.get("result_summary"):
            try:
                it["result_summary_obj"] = json.loads(it.get("result_summary") or "{}")
            except Exception:
                it["result_summary_obj"] = None

    return render_template(
        "system/history.html",
        title="系统管理 - 排产历史",
        versions=versions,
        selected=selected,
        selected_summary=selected_summary,
        items=items,
        filters={"version": version_raw, "limit": str(limit)},
    )

