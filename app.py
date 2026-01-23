import atexit
import json
import os
from flask import Flask, g
from markupsafe import Markup

from config import config as config_map
from core.infrastructure.logging import AppLogger, OperationLogger
from core.infrastructure.errors import register_error_handlers
from core.infrastructure.database import get_connection, ensure_schema
from core.infrastructure.backup import BackupManager
from core.services.common.excel_templates import ensure_excel_templates

from web.routes.dashboard import bp as dashboard_bp
from web.routes.excel_demo import bp as excel_demo_bp
from web.routes.personnel import bp as personnel_bp
from web.routes.equipment import bp as equipment_bp
from web.routes.process import bp as process_bp
from web.routes.scheduler import bp as scheduler_bp
from web.routes.system import bp as system_bp


def create_app() -> Flask:
    env = os.environ.get("APS_ENV") or "default"
    cfg_class = config_map.get(env) or config_map["default"]

    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(cfg_class)

    # Jinja 过滤器：JSON 输出（确保中文可读）
    def tojson_zh(value, indent: int = 2):
        return Markup(json.dumps(value, ensure_ascii=False, indent=indent))

    app.jinja_env.filters["tojson_zh"] = tojson_zh

    # 运行目录确保存在（打包后也依赖这些目录）
    os.makedirs(os.path.dirname(app.config["DATABASE_PATH"]), exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)
    os.makedirs(app.config["EXCEL_TEMPLATE_DIR"], exist_ok=True)

    # Excel 模板：按开发文档交付要求，确保 templates_excel/ 下有固定模板文件（缺失则生成）
    try:
        stats = ensure_excel_templates(app.config["EXCEL_TEMPLATE_DIR"])
        if stats.get("created"):
            app.logger.info(f"已生成 Excel 模板：{len(stats.get('created', []))} 个")
    except Exception as e:
        # 不阻断启动：模板下载接口仍可动态生成兜底
        app.logger.warning(f"生成 Excel 模板失败（将使用动态模板兜底）：{e}")

    # 文件日志（用户可用于排障：中文信息）
    app_logger = AppLogger(
        app_name=app.config.get("APP_NAME", "APS"),
        log_dir=app.config["LOG_DIR"],
        log_level=app.config.get("LOG_LEVEL", "INFO"),
        max_bytes=app.config.get("LOG_MAX_BYTES", 10 * 1024 * 1024),
        backup_count=app.config.get("LOG_BACKUP_COUNT", 5),
    )
    app.logger.handlers = app_logger.logger.handlers
    app.logger.setLevel(app_logger.logger.level)

    # DB schema
    ensure_schema(app.config["DATABASE_PATH"], app.logger)

    # 每请求 DB 连接（避免跨线程）
    @app.before_request
    def _open_db():
        if "db" not in g:
            g.db = get_connection(app.config["DATABASE_PATH"])
            g.op_logger = OperationLogger(g.db, logger=app.logger)

    @app.teardown_appcontext
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                db.close()
            except Exception:
                pass

    # 错误处理（接口返回结构统一；提示信息中文）
    register_error_handlers(app)

    # 路由
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(excel_demo_bp, url_prefix="/excel-demo")
    app.register_blueprint(personnel_bp, url_prefix="/personnel")
    app.register_blueprint(equipment_bp, url_prefix="/equipment")
    app.register_blueprint(process_bp, url_prefix="/process")
    app.register_blueprint(scheduler_bp, url_prefix="/scheduler")
    app.register_blueprint(system_bp, url_prefix="/system")

    # 退出自动备份（不启后台线程）
    backup_manager = BackupManager(
        db_path=app.config["DATABASE_PATH"],
        backup_dir=app.config["BACKUP_DIR"],
        keep_days=app.config.get("BACKUP_KEEP_DAYS", 7),
        logger=app.logger,
    )

    def _backup_on_exit():
        try:
            backup_manager.backup(suffix="auto")
        except Exception as e:
            # 退出阶段尽量不抛错，记录到错误日志即可
            app.logger.error(f"退出自动备份失败：{e}")

    atexit.register(_backup_on_exit)

    app.logger.info("应用启动完成。")
    return app


app = create_app()


if __name__ == "__main__":
    # Win7 本地运行（开发/调试）；打包后用 exe 启动
    app.run(host="127.0.0.1", port=5000, debug=app.config.get("DEBUG", False))

