from __future__ import annotations

import os
import sqlite3
from typing import Any, Dict, List, Optional

from flask import current_app, flash, g, redirect, request, url_for

from core.infrastructure.backup import MaintenanceWindowError, maintenance_window
from core.infrastructure.database import ensure_schema
from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.infrastructure.logging import OperationLogger
from core.services.system import SystemConfigService
from web.ui_mode import render_ui_template as render_template

from .system_bp import bp
from .system_utils import _get_backup_manager, _get_job_state_map, _get_system_cfg_snapshot, _validate_backup_filename


def _user_maintenance_message(err: MaintenanceWindowError) -> str:
    if getattr(err, "code", "") == "busy":
        return str(getattr(err, "message", "") or "数据库正在维护/恢复中，请稍后重试。")
    return "系统维护锁处理失败，请查看日志后稍后重试。"


@bp.get("/")
def index():
    return redirect(url_for("system.backup_page"))


@bp.get("/backup")
def backup_page():
    cfg = _get_system_cfg_snapshot()
    keep_days = int(cfg.auto_backup_keep_days)
    mgr = _get_backup_manager(keep_days=keep_days)
    backups = mgr.list_backups()
    from core.services.system import SystemMaintenanceService

    plugin_status = current_app.config.get("PLUGIN_STATUS")
    return render_template(
        "system/backup.html",
        title="系统管理 - 备份/恢复",
        backups=backups,
        keep_days=keep_days,
        settings=cfg.to_dict(),
        job_state=_get_job_state_map(),
        plugin_status=plugin_status,
        maintenance_limits={
            "max_backup_delete_per_run": int(SystemMaintenanceService.MAX_BACKUP_DELETE_PER_RUN),
        },
    )


@bp.post("/backup/create")
def backup_create():
    cfg = _get_system_cfg_snapshot()
    mgr = _get_backup_manager(keep_days=int(cfg.auto_backup_keep_days))
    try:
        path = mgr.backup(suffix="manual")
    except MaintenanceWindowError as e:
        if e.code != "busy":
            current_app.logger.error("手动备份触发维护锁异常：code=%s message=%s", e.code, e.message)
        flash(_user_maintenance_message(e), "warning" if e.code == "busy" else "error")
        return redirect(url_for("system.backup_page"))
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
    保存备份页的自动任务设置。

    说明：
    - 自动备份：按请求触发
    - 正常退出时的退出备份：与 auto_backup_enabled 共用同一开关
    - 自动清理备份：按请求触发
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
    except Exception:
        current_app.logger.exception("删除备份失败（filename=%s）", filename)
        flash("删除备份失败，请稍后重试。", "error")
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
    failed_details: List[str] = []
    deleted: List[str] = []
    for raw in filenames:
        try:
            fn = _validate_backup_filename(raw)
        except ValidationError as e:
            shown = str(raw or "").strip() or "（空）"
            failed.append(shown)
            failed_details.append(f"{shown}: {e.message}")
            continue
        p = os.path.join(backup_dir, fn)
        if not os.path.exists(p):
            failed.append(fn)
            failed_details.append(f"{fn}: 文件不存在")
            continue
        try:
            os.remove(p)
            ok += 1
            deleted.append(fn)
        except Exception:
            current_app.logger.exception("批量删除备份失败（filename=%s）", fn)
            failed.append(fn)
            failed_details.append(f"{fn}: 删除失败，请查看日志")
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
        sample = "；".join(failed_details[:10])
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
    try:
        with maintenance_window(current_app.config["DATABASE_PATH"], logger=current_app.logger, action="restore_flow"):
            result = mgr.restore(backup_path)
            if not result.ok:
                flash(result.message, "warning" if result.code == "busy" else "error")
                return redirect(url_for("system.backup_page"))

            # 恢复后确保 schema（索引/新表）：
            # 这里必须与 restore 处于同一 maintenance window，避免刚恢复完就被并发请求打断。
            try:
                ensure_schema(
                    current_app.config["DATABASE_PATH"],
                    current_app.logger,
                    backup_dir=current_app.config.get("BACKUP_DIR"),
                )
            except Exception:
                current_app.logger.exception("恢复后 ensure_schema 失败")
                flash("数据库文件已恢复，但后续结构检查失败，请查看日志后再继续使用。", "error")
                return redirect(url_for("system.backup_page"))
    except MaintenanceWindowError as e:
        if e.code != "busy":
            current_app.logger.error("数据库恢复触发维护锁异常：code=%s message=%s", e.code, e.message)
        flash(_user_maintenance_message(e), "warning" if e.code == "busy" else "error")
        return redirect(url_for("system.backup_page"))

    # 写入操作日志（独立连接）
    conn = None
    try:
        before_restore_path = getattr(result, "before_restore_path", None)
        conn = sqlite3.connect(current_app.config["DATABASE_PATH"])
        op_logger = OperationLogger(conn, logger=current_app.logger)
        logged = op_logger.info(
            module="system",
            action="restore",
            target_type="backup",
            target_id=filename,
            detail={
                "filename": filename,
                "note": "已恢复数据库；恢复前自动备份 before_restore 已执行，且后续 ensure_schema 已成功完成。",
                "before_restore_filename": os.path.basename(before_restore_path) if isinstance(before_restore_path, str) and before_restore_path else None,
            },
        )
        if not logged:
            current_app.logger.warning("恢复成功留痕写入 OperationLogs 失败：filename=%s", filename)
    except Exception:
        current_app.logger.exception("恢复后写入操作日志失败（不阻断）")
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    current_app.logger.info("数据库恢复流程完成：%s", filename)
    flash(f"已从备份恢复：{filename}。建议刷新页面/重新打开浏览器以加载最新数据。", "success")
    return redirect(url_for("system.backup_page"))

