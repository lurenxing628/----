import atexit
import json
import os
import sys
from flask import Flask, g, request

from config import config as config_map
from core.infrastructure.logging import AppLogger, OperationLogger
from web.error_handlers import register_error_handlers
from web.ui_mode import init_ui_mode
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
from web.bootstrap.factory import create_app_core
from web.bootstrap.launcher import pick_bind_host, pick_port, write_runtime_host_port_files
from web.bootstrap.paths import runtime_base_dir


# atexit 退出备份去重：避免 create_app() 在测试/脚本中被多次调用导致重复注册
_EXIT_BACKUP_MANAGER = None
_EXIT_BACKUP_REGISTERED = False


def _runtime_base_dir() -> str:
    return runtime_base_dir(anchor_file=__file__)


def _create_app_legacy() -> Flask:
    # 默认环境：
    # - 源码运行：development（便于调试）
    # - PyInstaller 打包后：production（避免 reloader/调试模式带来的多进程与副作用）
    env = (os.environ.get("APS_ENV") or "").strip().lower()
    if not env:
        env = "production" if getattr(sys, "frozen", False) else "default"
    cfg_class = config_map.get(env) or config_map["default"]

    base_dir = _runtime_base_dir()
    # 注意：static/templates 仍使用原目录；V2 新 UI 通过 init_ui_mode 的 overlay + /static-v2 注入
    static_dir = os.path.join(base_dir, "static")
    templates_dir = os.path.join(base_dir, "templates")

    # 注意：打包后 templates/static 与 exe 同目录，因此这里用绝对路径，避免 Flask 以模块 root_path 为基准导致找不到资源
    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
    app.config.from_object(cfg_class)

    # Jinja 过滤器：JSON 输出（确保中文可读）
    def tojson_zh(value, indent: int = 2):
        # 返回普通字符串，让 Jinja autoescape 生效，避免 detail 中含 HTML 时被当作 Markup 直出（潜在 XSS）
        return json.dumps(value, ensure_ascii=False, indent=indent)

    app.jinja_env.filters["tojson_zh"] = tojson_zh

    # 文件日志（用户可用于排障：中文信息）
    # 注意：尽量提前接管 app.logger（覆盖 init_ui_mode / ensure_schema / 插件加载等早期日志）
    app_logger = AppLogger(
        app_name=app.config.get("APP_NAME", "APS"),
        log_dir=app.config["LOG_DIR"],
        log_level=app.config.get("LOG_LEVEL", "INFO"),
        max_bytes=app.config.get("LOG_MAX_BYTES", 10 * 1024 * 1024),
        backup_count=app.config.get("LOG_BACKUP_COUNT", 5),
    )
    app.logger.handlers = app_logger.logger.handlers
    app.logger.setLevel(app_logger.logger.level)

    # UI 模式（V1/V2）：注册 /static-v2 与模板 overlay（便于复用同一套 V2 模板）
    init_ui_mode(app, base_dir)

    # 运行目录确保存在（打包后也依赖这些目录）
    # 防御：DATABASE_PATH 可能是纯文件名（dirname 为空串时 makedirs 会报错）
    db_dir = os.path.dirname(app.config["DATABASE_PATH"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
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

    # 更新“退出备份”引用（以最新 create_app() 为准）
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
                # 退出阶段尽量不抛错，记录到错误日志即可
                try:
                    bm.logger.error(f"退出自动备份失败：{e}")
                except Exception:
                    pass

        atexit.register(_backup_on_exit)
        _EXIT_BACKUP_REGISTERED = True

    app.logger.info("应用启动完成 (UI Test Mode)。")
    return app


def create_app() -> Flask:
    # new_ui 入口先统一最小安全基线（SECRET_KEY），其余安全策略差异后续再显式收敛。
    return create_app_core(
        ui_mode="new_ui",
        enable_secret_key=True,
        enable_security_headers=False,
        enable_session_cookie_hardening=False,
    )


app = create_app()


if __name__ == "__main__":
    # Win7 本地运行（开发/调试）；打包后用 exe 启动
    # 端口策略（避免“端口被占用/受限就无法启动”）：
    # - 优先使用 APS_PORT（若提供）
    # - 否则优先 5000
    # - 若绑定失败（WinError 10013/10048 等），自动选择可用端口，并写入 logs/aps_port.txt
    # 仅支持 IPv4；若 APS_HOST 非法/IPv6/hostname，则回退到 127.0.0.1
    raw_host = os.environ.get("APS_HOST")
    host = pick_bind_host(raw_host, logger=app.logger)

    raw_port = os.environ.get("APS_PORT")
    preferred_port = 5000
    if raw_port is not None and str(raw_port).strip() != "":
        try:
            preferred_port = int(str(raw_port).strip())
        except Exception:
            preferred_port = 5000

    requested_host = host
    host, port = pick_port(host, preferred_port, logger=app.logger)
    if host != requested_host:
        try:
            app.logger.warning(f"APS_HOST={requested_host} 不可绑定，已回退到 {host}（port={port}）")
        except Exception:
            pass

    try:
        os.environ["APS_HOST"] = str(host)
        os.environ["APS_PORT"] = str(int(port))
    except Exception:
        pass

    # 写入启动信息文件契约：
    # - logs/aps_port.txt：仅端口数字 + 换行
    # - logs/aps_host.txt：实际可访问 host + 换行
    try:
        write_runtime_host_port_files(
            runtime_dir=_runtime_base_dir(),
            cfg_log_dir=app.config.get("LOG_DIR"),
            host=host,
            port=port,
            logger=app.logger,
        )
    except Exception as e:
        try:
            app.logger.warning(f"写入启动信息文件失败（已忽略）：{e}")
        except Exception:
            pass

    debug = bool(app.config.get("DEBUG", False))
    use_reloader = debug and not getattr(sys, "frozen", False)
    app.run(host=host, port=port, debug=debug, use_reloader=use_reloader)
