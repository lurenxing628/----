from __future__ import annotations

import atexit
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

from flask import Flask, g, request

from config import config as config_map
from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.logging import AppLogger, OperationLogger
from core.infrastructure.migrations.common import fallback_log
from core.models.enums import YesNo
from core.services.common.excel_templates import ensure_excel_templates
from web.error_handlers import register_error_handlers
from web.routes.dashboard import bp as dashboard_bp
from web.routes.equipment import bp as equipment_bp
from web.routes.excel_demo import bp as excel_demo_bp
from web.routes.material import bp as material_bp
from web.routes.personnel import bp as personnel_bp
from web.routes.process import bp as process_bp
from web.routes.reports import bp as reports_bp
from web.routes.scheduler import bp as scheduler_bp
from web.routes.system import bp as system_bp
from web.ui_mode import init_ui_mode

from .paths import runtime_base_dir
from .plugins import bootstrap_plugins
from .security import apply_session_cookie_hardening, ensure_secret_key, register_security_headers
from .static_versioning import install_versioned_url_for

# atexit 退出备份去重：避免 create_app_core() 在测试/脚本中被多次调用导致重复注册
_EXIT_BACKUP_MANAGER = None
_EXIT_BACKUP_REGISTERED = False


def _apply_runtime_config(app: Flask, *, base_dir: str) -> None:
    app.config["BASE_DIR"] = base_dir
    app.config["DATABASE_PATH"] = (os.environ.get("APS_DB_PATH") or os.path.join(base_dir, "db", "aps.db"))
    app.config["LOG_DIR"] = (os.environ.get("APS_LOG_DIR") or os.path.join(base_dir, "logs"))
    app.config["BACKUP_DIR"] = (os.environ.get("APS_BACKUP_DIR") or os.path.join(base_dir, "backups"))
    app.config["EXCEL_TEMPLATE_DIR"] = (
        os.environ.get("APS_EXCEL_TEMPLATE_DIR") or os.path.join(base_dir, "templates_excel")
    )


def _should_register_exit_backup(*, debug: bool, frozen: Optional[bool] = None, run_main: Optional[str] = None) -> bool:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not debug or is_frozen:
        return True
    marker = os.environ.get("WERKZEUG_RUN_MAIN") if run_main is None else run_main
    return str(marker or "").strip().lower() == "true"


def _is_exit_backup_enabled(bm: BackupManager) -> Optional[bool]:
    conn = None
    try:
        conn = get_connection(bm.db_path)
        from core.services.system import SystemConfigService

        cfg = SystemConfigService(conn, logger=bm.logger).get_snapshot_readonly(
            backup_keep_days_default=int(getattr(bm, "keep_days", 7) or 7)
        )
        return cfg.auto_backup_enabled == YesNo.YES.value
    except Exception as e:
        fallback_log(bm.logger, "error", f"读取退出自动备份配置失败：{e}")
        return None
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _run_exit_backup(manager: Optional[BackupManager] = None) -> bool:
    bm = manager or _EXIT_BACKUP_MANAGER
    if bm is None:
        return False
    enabled = _is_exit_backup_enabled(bm)
    if enabled is not True:
        if enabled is None:
            fallback_log(bm.logger, "warning", "退出自动备份已跳过：读取配置失败。")
        else:
            fallback_log(bm.logger, "info", "退出自动备份已跳过：auto_backup_enabled=no。")
        return False
    try:
        bm.backup(suffix="exit")
        return True
    except Exception as e:
        fallback_log(bm.logger, "error", f"退出自动备份失败：{e}")
        return False


def _default_anchor_file() -> str:
    # 源码布局固定：web/bootstrap/factory.py 向上两级即仓库根目录
    return str(Path(__file__).resolve().parents[2] / "app.py")


def create_app_core(
    *,
    ui_mode: str,
    enable_secret_key: bool,
    enable_security_headers: bool,
    enable_session_cookie_hardening: bool,
) -> Flask:
    # 默认环境：
    # - 源码运行：development（便于调试）
    # - PyInstaller 打包后：production（避免 reloader/调试模式带来的多进程与副作用）
    env = (os.environ.get("APS_ENV") or "").strip().lower()
    if not env:
        env = "production" if getattr(sys, "frozen", False) else "default"
    cfg_class = config_map.get(env) or config_map["default"]

    base_dir = runtime_base_dir(anchor_file=_default_anchor_file())
    static_dir = os.path.join(base_dir, "static")
    templates_dir = os.path.join(base_dir, "templates")

    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
    app.config.from_object(cfg_class)
    _apply_runtime_config(app, base_dir=base_dir)
    app.config["APP_UI_MODE"] = ui_mode
    # 静态资源长缓存（配合 url_for('static', ...) 版本参数）
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = int(app.config.get("SEND_FILE_MAX_AGE_DEFAULT") or 43200)
    install_versioned_url_for(app, static_dir)

    def tojson_zh(value, indent: int = 2):
        return json.dumps(value, ensure_ascii=False, indent=indent)

    app.jinja_env.filters["tojson_zh"] = tojson_zh

    app_logger = AppLogger(
        app_name=app.config.get("APP_NAME", "APS"),
        log_dir=app.config["LOG_DIR"],
        log_level=app.config.get("LOG_LEVEL", "INFO"),
        max_bytes=app.config.get("LOG_MAX_BYTES", 10 * 1024 * 1024),
        backup_count=app.config.get("LOG_BACKUP_COUNT", 5),
    )
    app.logger.handlers = app_logger.logger.handlers
    app.logger.setLevel(app_logger.logger.level)

    if enable_secret_key:
        ensure_secret_key(app)
    if enable_session_cookie_hardening:
        apply_session_cookie_hardening(app)

    init_ui_mode(app, base_dir)

    db_dir = os.path.dirname(app.config["DATABASE_PATH"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)
    os.makedirs(app.config["EXCEL_TEMPLATE_DIR"], exist_ok=True)

    try:
        stats = ensure_excel_templates(app.config["EXCEL_TEMPLATE_DIR"])
        if stats.get("created"):
            app.logger.info(f"已生成 Excel 模板：{len(stats.get('created', []))} 个")
    except Exception as e:
        app.logger.warning(f"生成 Excel 模板失败（将使用动态模板兜底）：{e}")

    schema_path = os.path.abspath(os.path.join(base_dir, "schema.sql"))
    ensure_schema(
        app.config["DATABASE_PATH"],
        app.logger,
        schema_path=schema_path if os.path.exists(schema_path) else None,
        backup_dir=app.config.get("BACKUP_DIR"),
    )

    plugin_status = bootstrap_plugins(
        base_dir,
        app.config["DATABASE_PATH"],
        logger=app.logger,
    )
    app.config["PLUGIN_STATUS"] = plugin_status

    @app.before_request
    def _open_db():
        try:
            g._aps_req_started = time.perf_counter()
        except Exception:
            g._aps_req_started = None
        try:
            if request.path and str(request.path).startswith("/static"):
                return
        except Exception:
            pass
        if "db" not in g:
            g.db = get_connection(app.config["DATABASE_PATH"])
            g.op_logger = OperationLogger(g.db, logger=app.logger)
            try:
                from core.services.system import SystemMaintenanceService

                _ = SystemMaintenanceService.run_if_due(
                    g.db,
                    db_path=app.config["DATABASE_PATH"],
                    backup_dir=app.config["BACKUP_DIR"],
                    backup_keep_days_default=int(app.config.get("BACKUP_KEEP_DAYS", 7)),
                    logger=app.logger,
                    op_logger=getattr(g, "op_logger", None),
                )
            except Exception as e:
                app.logger.error(f"系统维护任务执行失败（已忽略）：{e}")

    @app.teardown_appcontext
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    if enable_security_headers:
        register_security_headers(app)

    @app.after_request
    def _perf_headers(resp):
        # 慢请求可观测：帮助区分“前端卡”与“后端慢”
        def _is_prefetch_req() -> bool:
            try:
                purpose = (request.headers.get("Purpose") or "").strip().lower()
                sec_purpose = (request.headers.get("Sec-Purpose") or "").strip().lower()
                x_moz = (request.headers.get("X-Moz") or "").strip().lower()
                return (
                    "prefetch" in purpose
                    or "prefetch" in sec_purpose
                    or x_moz == "prefetch"
                )
            except Exception:
                return False

        try:
            started = getattr(g, "_aps_req_started", None)
            if started is not None:
                total_ms = int((time.perf_counter() - float(started)) * 1000)
                resp.headers.setdefault("Server-Timing", f"app;dur={total_ms}")
                req_path = str(getattr(request, "path", "") or "")
                if total_ms >= 300 and not req_path.startswith("/static") and not _is_prefetch_req():
                    app.logger.warning(f"慢请求: {request.method} {request.path} {total_ms}ms")
        except Exception:
            pass
        return resp

    register_error_handlers(app)

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(excel_demo_bp, url_prefix="/excel-demo")
    app.register_blueprint(personnel_bp, url_prefix="/personnel")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(process_bp, url_prefix="/process")
    app.register_blueprint(scheduler_bp, url_prefix="/scheduler")
    app.register_blueprint(material_bp, url_prefix="/material")
    app.register_blueprint(reports_bp, url_prefix="/reports")
    app.register_blueprint(system_bp, url_prefix="/system")

    backup_manager = BackupManager(
        db_path=app.config["DATABASE_PATH"],
        backup_dir=app.config["BACKUP_DIR"],
        keep_days=app.config.get("BACKUP_KEEP_DAYS", 7),
        logger=app.logger,
    )

    global _EXIT_BACKUP_MANAGER, _EXIT_BACKUP_REGISTERED
    _EXIT_BACKUP_MANAGER = backup_manager

    if not _EXIT_BACKUP_REGISTERED and _should_register_exit_backup(debug=bool(app.config.get("DEBUG", False))):
        atexit.register(_run_exit_backup)
        _EXIT_BACKUP_REGISTERED = True
    elif not _EXIT_BACKUP_REGISTERED:
        app.logger.info("开发重载父进程跳过注册退出自动备份。")

    if str(ui_mode or "").strip().lower() == "new_ui":
        app.logger.info("应用启动完成 (UI Test Mode)。")
    else:
        app.logger.info("应用启动完成。")
    return app

