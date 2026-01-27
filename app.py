import atexit
import json
import os
import sys
from pathlib import Path
from flask import Flask, g, request
from markupsafe import Markup

from config import config as config_map
from core.infrastructure.logging import AppLogger, OperationLogger
from core.infrastructure.errors import register_error_handlers
from core.infrastructure.database import get_connection, ensure_schema
from core.infrastructure.backup import BackupManager
from core.services.common.excel_templates import ensure_excel_templates
from core.plugins import PluginManager, get_plugin_status

from web.routes.dashboard import bp as dashboard_bp
from web.routes.excel_demo import bp as excel_demo_bp
from web.routes.personnel import bp as personnel_bp
from web.routes.equipment import bp as equipment_bp
from web.routes.process import bp as process_bp
from web.routes.scheduler import bp as scheduler_bp
from web.routes.system import bp as system_bp
from web.routes.material import bp as material_bp
from web.routes.reports import bp as reports_bp


def _runtime_base_dir() -> str:
    """
    获取运行根目录：
    - 源码运行：仓库根目录（app.py 所在目录）
    - PyInstaller onedir：exe 所在目录
    """
    try:
        if getattr(sys, "frozen", False):
            return str(Path(sys.executable).resolve().parent)
        return str(Path(__file__).resolve().parent)
    except Exception:
        # 兜底：即使 __file__ 为相对路径/空串，也保证返回绝对路径且不为空
        if getattr(sys, "frozen", False):
            return os.path.abspath(os.path.dirname(sys.executable) or ".")
        return os.path.abspath(os.path.dirname(__file__ or "") or ".")


def create_app() -> Flask:
    env = os.environ.get("APS_ENV") or "default"
    cfg_class = config_map.get(env) or config_map["default"]

    base_dir = _runtime_base_dir()
    static_dir = os.path.join(base_dir, "static")
    templates_dir = os.path.join(base_dir, "templates")

    # 注意：打包后 templates/static 与 exe 同目录，因此这里用绝对路径，避免 Flask 以模块 root_path 为基准导致找不到资源
    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
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

    # DB schema（打包后 schema.sql 与 exe 同目录；若缺失则回退到默认路径）
    schema_path = os.path.abspath(os.path.join(base_dir, "schema.sql"))
    ensure_schema(
        app.config["DATABASE_PATH"],
        app.logger,
        schema_path=schema_path if os.path.exists(schema_path) else None,
        backup_dir=app.config.get("BACKUP_DIR"),
    )

    # 可选插件/可选依赖：vendor/ 注入 + plugins/ 动态加载（失败可回退，状态可观测）
    plugin_status = None
    conn0 = None
    try:
        conn0 = get_connection(app.config["DATABASE_PATH"])
    except Exception as e:
        conn0 = None
        try:
            app.logger.warning(f"打开数据库连接失败，插件加载将跳过配置落库：{e}")
        except Exception:
            pass

    # 只调用一次 load：避免异常路径重复加载导致状态不一致/重复副作用
    try:
        plugin_status = PluginManager.load_from_base_dir(base_dir, conn=conn0, logger=app.logger)
    except Exception as e:
        # 插件加载失败不阻断启动：保持可观测（系统页展示），并记录错误日志
        try:
            app.logger.error(f"插件加载失败（已忽略，启动继续）：{e}")
        except Exception:
            pass
        try:
            plugin_status = get_plugin_status()
        except Exception:
            plugin_status = None

    # 插件加载留痕：失败不影响启动，也不会触发重复加载
    if conn0 is not None:
        try:
            OperationLogger(conn0, logger=app.logger).info(
                "plugins",
                "load",
                target_type="runtime",
                target_id="plugins",
                detail=plugin_status,
            )
        except Exception:
            pass
        finally:
            try:
                conn0.close()
            except Exception:
                pass
    app.config["PLUGIN_STATUS"] = plugin_status

    # 每请求 DB 连接（避免跨线程）
    @app.before_request
    def _open_db():
        # 静态资源不需要 DB（减少不必要开销，也避免触发自动维护）
        try:
            if request.path and str(request.path).startswith("/static"):
                return
        except Exception:
            pass
        if "db" not in g:
            g.db = get_connection(app.config["DATABASE_PATH"])
            g.op_logger = OperationLogger(g.db, logger=app.logger)
            # 系统维护（按请求触发：自动备份/自动清理等；内部带节流）
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
                # 不阻断请求：只记错误日志
                app.logger.error(f"系统维护任务执行失败（已忽略）：{e}")

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
    app.register_blueprint(material_bp, url_prefix="/material")
    app.register_blueprint(reports_bp, url_prefix="/reports")
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

