from __future__ import annotations

import os
import sqlite3
from typing import Any, List, Optional

from flask import current_app, flash, g, redirect, render_template, request, url_for

from core.infrastructure.backup import MaintenanceWindowError
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import AppError, ErrorCode, ValidationError
from core.infrastructure.logging import OperationLogger
from core.infrastructure.safe_files import UnsafeFixedFileError, remove_fixed_file
from web.routes.form_values import form_yes_no_value
from web.viewmodels.system_backup_page import build_system_backup_page_view_model

from .system_backup_actions import run_backup_restore
from .system_bp import bp
from .system_utils import (
    _get_backup_manager,
    _get_job_state_map,
    _get_system_cfg_snapshot,
    _get_system_config_service,
    _validate_backup_filename,
)


def _user_maintenance_message(err: MaintenanceWindowError) -> str:
    if getattr(err, "code", "") == "busy":
        return str(getattr(err, "message", "") or "数据库正在维护/恢复中，请稍后重试。")
    return "系统维护锁处理失败，请查看日志后稍后重试。"


def _redirect_restore_maintenance_error(err: MaintenanceWindowError):
    if err.code != "busy":
        current_app.logger.error("数据库恢复触发维护锁异常：code=%s message=%s", err.code, err.message)
    flash(_user_maintenance_message(err), "warning" if err.code == "busy" else "error")
    return redirect(url_for("system.backup_page"))


def _write_restore_success_log(filename: str, result: Any):
    conn = None
    before_restore_path = getattr(result, "before_restore_path", None)
    try:
        conn = get_connection(current_app.config["DATABASE_PATH"])
        op_logger = OperationLogger(conn, logger=current_app.logger)
        logged = op_logger.info(
            module="system",
            action="restore",
            target_type="backup",
            target_id=filename,
            detail={
                "filename": filename,
                "restore_code": str(getattr(result, "code", "") or "verified"),
                "note": "数据库文件已恢复并完成结构校验；恢复前自动备份 before_restore 已执行。",
                "before_restore_filename": os.path.basename(before_restore_path)
                if isinstance(before_restore_path, str) and before_restore_path
                else None,
            },
        )
        if not logged:
            current_app.logger.warning("恢复成功留痕写入 OperationLogs 失败：filename=%s", filename)
        return conn
    except Exception:
        current_app.logger.exception("恢复后写入操作日志失败（不阻断）")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                current_app.logger.exception("恢复后操作日志连接关闭失败（不阻断）")
        return None


@bp.get("/")
def index():
    return redirect(url_for("system.backup_page"))


@bp.get("/backup")
def backup_page():
    cfg = _get_system_cfg_snapshot()
    keep_days = int(cfg.auto_backup_keep_days)
    mgr = _get_backup_manager(keep_days=keep_days)
    backups = mgr.list_backups()
    backup_list_unsafe_count = int(getattr(mgr, "last_list_unsafe_count", 0) or 0)
    backup_list_unsafe_sample = list(getattr(mgr, "last_list_unsafe_sample", []) or [])
    backup_list_error_count = int(getattr(mgr, "last_list_error_count", 0) or 0)
    backup_list_error_sample = list(getattr(mgr, "last_list_error_sample", []) or [])
    from core.services.system import SystemMaintenanceService

    plugin_status = current_app.config.get("PLUGIN_STATUS")
    settings = cfg.to_dict()
    return render_template(
        "system/backup.html",
        title="系统管理 - 备份/恢复",
        backups=backups,
        backup_list_unsafe_count=backup_list_unsafe_count,
        backup_list_unsafe_sample=backup_list_unsafe_sample,
        backup_list_error_count=backup_list_error_count,
        backup_list_error_sample=backup_list_error_sample,
        keep_days=keep_days,
        settings=settings,
        job_state=_get_job_state_map(),
        page=build_system_backup_page_view_model(settings, plugin_status),
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
    except RuntimeError as e:
        # 备份完整性检查执行失败/未通过会抛裸 RuntimeError（R32/O27：坏库绝不升正式、loud 不静默）。
        # MaintenanceWindowError 是 RuntimeError 子类、已在上面拦截；此处兜的是完整性检查类失败——
        # 必须转成具体中文，别让用户只看到 errorhandler(500) 的笼统「服务器内部错误，请查看日志」。
        current_app.logger.error("手动备份失败（完整性检查未通过，已放弃本次备份以保护数据）：%s", e)
        flash("备份完整性检查失败，已放弃本次备份以保护数据，请查看日志。", "error")
        return redirect(url_for("system.backup_page"))
    except (sqlite3.OperationalError, OSError) as e:
        # 备份写入阶段的预期运行时失败：sqlite connect/backup 的磁盘满/库被占用/无法打开抛
        # sqlite3.OperationalError、临时文件原子替换抛 OSError（磁盘满/无写入权限）——都不是
        # RuntimeError 子类，若不在此拦截会落到 errorhandler(500) 笼统「服务器内部错误」，用户
        # 看不到这条具体中文提示。只兜 OperationalError（不兜 ProgrammingError/InterfaceError
        # 等编程错误——那些是 bug，必须 loud 透到 500 不被伪装成「磁盘空间不足」）；logger.exception
        # 留真实堆栈便于排查。
        current_app.logger.exception("手动备份写入失败（已放弃本次备份以保护数据）：%s", e)
        flash("备份写入失败（磁盘空间不足、数据库被占用或无写入权限），已放弃本次备份，请查看日志。", "error")
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
    try:
        svc = _get_system_config_service()
        svc.update_backup_settings(
            auto_backup_enabled=form_yes_no_value(request.form, "auto_backup_enabled"),
            auto_backup_interval_minutes=request.form.get("auto_backup_interval_minutes"),
            auto_backup_cleanup_enabled=form_yes_no_value(request.form, "auto_backup_cleanup_enabled"),
            auto_backup_keep_days=request.form.get("auto_backup_keep_days"),
            auto_backup_cleanup_interval_minutes=request.form.get("auto_backup_cleanup_interval_minutes"),
        )
        flash("备份自动任务设置已保存。", "success")
    except AppError as e:
        flash(e.message, "error")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/delete")
def backup_delete():
    filename = _validate_backup_filename(request.form.get("filename") or "")
    backup_dir = current_app.config["BACKUP_DIR"]
    backup_path = os.path.join(backup_dir, filename)
    try:
        remove_fixed_file(backup_path, missing_ok=False, allow_symlink=False)
        if getattr(g, "op_logger", None) is not None:
            try:
                g.op_logger.info(
                    module="system",
                    action="backup_delete",
                    target_type="backup",
                    target_id=filename,
                    detail={"filename": filename, "mode": "manual"},
                )
            except Exception:
                # 备份文件已经删除成功，留痕失败只记录日志，不把成功操作改成失败。
                current_app.logger.exception("删除备份成功后写入操作日志失败（不阻断）")
        flash(f"已删除备份：{filename}", "success")
    except FileNotFoundError:
        flash(f"备份文件不存在：{filename}", "error")
    except UnsafeFixedFileError as exc:
        current_app.logger.warning("拒绝删除不安全备份文件（filename=%s）：%s", filename, exc)
        flash("删除备份失败：备份文件不是安全的普通文件，请先检查备份目录。", "error")
    except OSError:
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
        try:
            remove_fixed_file(p, missing_ok=False, allow_symlink=False)
            ok += 1
            deleted.append(fn)
        except FileNotFoundError:
            failed.append(fn)
            failed_details.append(f"{fn}: 文件不存在")
            continue
        except UnsafeFixedFileError as exc:
            current_app.logger.warning("拒绝批量删除不安全备份文件（filename=%s）：%s", fn, exc)
            failed.append(fn)
            failed_details.append(f"{fn}: 不是安全的普通备份文件")
            continue
        except OSError:
            current_app.logger.exception("批量删除备份失败（filename=%s）", fn)
            failed.append(fn)
            failed_details.append(f"{fn}: 删除失败，请查看日志")
            continue

    if getattr(g, "op_logger", None) is not None:
        try:
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
        except Exception:
            # 批量删除结果已经确定，留痕失败只记录日志，不影响用户看到删除结果。
            current_app.logger.exception("批量删除备份后写入操作日志失败（不阻断）")

    flash(f"批量删除完成：成功 {ok}，失败 {len(failed)}。", "success" if ok else "warning")
    if failed:
        sample = "；".join(failed_details[:10])
        flash(f"删除失败（最多展示 10 个）：{sample}", "warning")
    return redirect(url_for("system.backup_page"))


@bp.post("/backup/cleanup")
def backup_cleanup():
    cfg = _get_system_cfg_snapshot()
    mgr = _get_backup_manager(keep_days=int(cfg.auto_backup_keep_days))
    cleanup_result = mgr.cleanup_old_backups() or {}
    removed = int(cleanup_result.get("removed_count") or 0)
    unsafe_count = int(cleanup_result.get("unsafe_count") or 0)
    error_count = int(cleanup_result.get("error_count") or 0)

    if getattr(g, "op_logger", None) is not None:
        g.op_logger.info(
            module="system",
            action="cleanup",
            target_type="backup",
            target_id=None,
            detail={
                "keep_days": int(mgr.keep_days),
                "removed_count": int(removed),
                "unsafe_count": unsafe_count,
                "error_count": error_count,
                "mode": "manual",
            },
        )

    flash(f"已清理过期备份：删除 {removed} 个（保留 {mgr.keep_days} 天内的备份）。", "success")
    if unsafe_count:
        sample = "；".join(str(item.get("filename") or "") for item in list(cleanup_result.get("unsafe_sample") or [])[:10])
        flash(f"有 {unsafe_count} 个备份文件不是安全的普通文件，已跳过：{sample}", "warning")
    if error_count:
        sample = "；".join(str(item.get("filename") or "") for item in list(cleanup_result.get("error_sample") or [])[:10])
        flash(f"有 {error_count} 个备份文件清理失败，请检查日志：{sample}", "warning")
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

    try:
        outcome = run_backup_restore(
            filename=filename,
            backup_path=backup_path,
            database_path=current_app.config["DATABASE_PATH"],
            backup_dir=current_app.config.get("BACKUP_DIR"),
            manager=_get_backup_manager(),
            logger=current_app.logger,
            ensure_schema_func=ensure_schema,
        )
    except MaintenanceWindowError as e:
        return _redirect_restore_maintenance_error(e)

    if outcome.category == "success":
        result = outcome.result
        conn = _write_restore_success_log(filename, result)
        try:
            current_app.logger.info("数据库恢复流程完成：%s", filename)
        except Exception:
            current_app.logger.exception("恢复完成日志写入失败（不阻断）")
        try:
            current_app.logger.info("数据库恢复操作日志连接准备关闭：%s", filename)
        except Exception:
            current_app.logger.exception("恢复操作日志连接关闭前记录失败（不阻断）")
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    flash(outcome.message, outcome.category)
    return redirect(url_for("system.backup_page"))
