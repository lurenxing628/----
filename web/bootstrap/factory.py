from __future__ import annotations

import atexit
import json
import os
import sys
from pathlib import Path

from flask import Flask, g, request

from config import config as config_map
from core.infrastructure.backup import BackupManager
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.logging import AppLogger, OperationLogger
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

# atexit 退出备份去重：避免 create_app_core() 在测试/脚本中被多次调用导致重复注册
_EXIT_BACKUP_MANAGER = None
_EXIT_BACKUP_REGISTERED = False


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
    app.config["APP_UI_MODE"] = ui_mode

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

    if not _EXIT_BACKUP_REGISTERED:

        def _backup_on_exit():
            bm = _EXIT_BACKUP_MANAGER
            if bm is None:
                return
            try:
                bm.backup(suffix="auto")
            except Exception as e:
                try:
                    bm.logger.error(f"退出自动备份失败：{e}")
                except Exception:
                    pass

        atexit.register(_backup_on_exit)
        _EXIT_BACKUP_REGISTERED = True

    if str(ui_mode or "").strip().lower() == "new_ui":
        app.logger.info("应用启动完成 (UI Test Mode)。")
    else:
        app.logger.info("应用启动完成。")
    return app

