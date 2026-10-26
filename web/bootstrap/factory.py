from __future__ import annotations

import atexit
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any, Optional, cast

from flask import Flask, current_app, g, request
from werkzeug.serving import ThreadedWSGIServer

from core.infrastructure.backup import is_maintenance_window_active
from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.logging import AppLogger, OperationLogger, safe_log
from web.error_boundary import (
    render_error_template,
    wants_json_error_response,
)
from web.error_handlers import register_error_handlers
from web.routes.workbench.legacy_blueprints import register_legacy_blueprints
from web.routes.workbench.legacy_dispatch import install_legacy_retirement
from web.routes.workbench.registration import bp as workbench_bp
from web.runtime_host import install_runtime_host

from .app_config import config as _config_map
from .json_provider import StrictJSONProvider
from .launcher_observability import launcher_log_warning
from .launcher_paths import is_portable_runtime, resolve_runtime_db_path, resolve_shared_data_root
from .launcher_shutdown import (
    RuntimeExitBackupManager,
    read_exit_backup_enabled,
    run_exit_backup,
)
from .paths import runtime_base_dir
from .plugins import bootstrap_plugins
from .runtime_server import create_runtime_server
from .schedule_config import bootstrap_schedule_config
from .security import apply_session_cookie_hardening, ensure_secret_key, register_security_headers
from .startup_config import resolve_config_class
from .static_versioning import install_versioned_url_for
from .workbench_request_lifecycle import (
    close_workbench_request_connection,
    install_workbench_request_lifecycle,
    track_workbench_request_connection,
)
from .workbench_request_lifecycle_wsgi import call_on_workbench_request_close
from .workbench_system_restore_recovery import prepare_system_restore_startup

# atexit 退出备份去重：避免 create_app_core() 在测试/脚本中被多次调用导致重复注册
_EXIT_BACKUP_MANAGER = None
_EXIT_BACKUP_REGISTERED = False
_RUNTIME_SERVER: Any = None
_RUNTIME_SERVER_LOCK = threading.Lock()
_RUNTIME_SERVER_SHUTDOWN_REQUESTED = False
_FACTORY_ONCE_FLAGS_KEY = "aps.factory.once_flags"


def resolve_startup_debug_flag() -> bool:
    # 此处只读同一配置源；锁归属判定仍先于 create_app 的数据库及退出备份副作用。
    return bool(resolve_config_class(_config_map).DEBUG)


def _app_log_once(app: Flask, key: str, level: str, message: str, *args: Any) -> None:
    flags = app.extensions.setdefault(_FACTORY_ONCE_FLAGS_KEY, set())
    if key in flags:
        return
    flags.add(key)
    safe_log(app.logger, level, message, *args)





def _apply_runtime_config(app: Flask, *, base_dir: str) -> None:
    app.config["BASE_DIR"] = base_dir
    if os.path.isfile(os.path.join(base_dir, "aps-complex-sample.txt")):
        app.config["WORKBENCH_INSTANCE_LABEL"] = "复杂样例 · 独立数据"
    data_root = resolve_shared_data_root(base_dir)
    overrides = {} if is_portable_runtime(base_dir) else os.environ
    app.config["DATABASE_PATH"] = resolve_runtime_db_path(base_dir)
    app.config["LOG_DIR"] = (overrides.get("APS_LOG_DIR") or os.path.join(data_root, "logs"))
    app.config["BACKUP_DIR"] = (overrides.get("APS_BACKUP_DIR") or os.path.join(data_root, "backups"))
    app.config["EXCEL_TEMPLATE_DIR"] = (
        overrides.get("APS_EXCEL_TEMPLATE_DIR") or os.path.join(data_root, "templates_excel")
    )


def should_use_runtime_reloader(debug: bool, frozen: Optional[bool] = None) -> bool:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    return bool(debug) and not is_frozen


def should_own_runtime_resources(
    debug: bool,
    frozen: Optional[bool] = None,
    run_main: Optional[str] = None,
) -> bool:
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    if not should_use_runtime_reloader(debug=bool(debug), frozen=is_frozen):
        return True
    marker = os.environ.get("WERKZEUG_RUN_MAIN") if run_main is None else run_main
    return str(marker or "").strip().lower() == "true"


def _run_exit_backup() -> bool:
    # 只由 _register_exit_backup 在赋值 _EXIT_BACKUP_MANAGER 之后注册到 atexit。
    return run_exit_backup(_EXIT_BACKUP_MANAGER, lambda target: read_exit_backup_enabled(target, get_connection))


def _maintenance_gate_response():
    message = "系统正在维护中，请稍后重试。"
    if wants_json_error_response():
        return {"success": False, "error": {"code": "503", "message": message}}, 503
    return render_error_template(title="系统维护中", message=message), 503


def _maintenance_detection_failure_response():
    message = "系统状态检测失败，请稍后重试。"
    if wants_json_error_response():
        return {"success": False, "error": {"code": "500", "message": message}}, 500
    return render_error_template(title="系统状态检测失败", message=message), 500


def _default_anchor_file() -> str:
    # 源码布局固定：web/bootstrap/factory.py 向上两级即仓库根目录
    return str(Path(__file__).resolve().parents[2] / "app.py")


def serve_runtime_app(app: Flask, host: str, port: int, *, server: Optional[ThreadedWSGIServer] = None) -> None:
    global _RUNTIME_SERVER, _RUNTIME_SERVER_SHUTDOWN_REQUESTED
    if server is None:
        server = cast(ThreadedWSGIServer, create_runtime_server(app, host, port))
    with _RUNTIME_SERVER_LOCK:
        _RUNTIME_SERVER = server
        _RUNTIME_SERVER_SHUTDOWN_REQUESTED = False
    try:
        server.serve_forever()
    finally:
        server.server_close()
        with _RUNTIME_SERVER_LOCK:
            _RUNTIME_SERVER = None
            _RUNTIME_SERVER_SHUTDOWN_REQUESTED = False


def request_runtime_server_shutdown(logger=None) -> bool:
    global _RUNTIME_SERVER_SHUTDOWN_REQUESTED
    with _RUNTIME_SERVER_LOCK:
        server = _RUNTIME_SERVER
        if server is None:
            return False
        if _RUNTIME_SERVER_SHUTDOWN_REQUESTED:
            return True
        _RUNTIME_SERVER_SHUTDOWN_REQUESTED = True

    def _shutdown() -> None:
        time.sleep(0.05)
        try:
            server.shutdown()
        except Exception as e:
            safe_log(logger, "warning", "请求运行时 Server 关闭失败：%s", e)

    threading.Thread(target=_shutdown, daemon=True).start()
    return True


def _ensure_runtime_dirs(app: Flask) -> None:
    db_dir = os.path.dirname(app.config["DATABASE_PATH"])
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    os.makedirs(app.config["LOG_DIR"], exist_ok=True)
    os.makedirs(app.config["BACKUP_DIR"], exist_ok=True)
    os.makedirs(app.config["EXCEL_TEMPLATE_DIR"], exist_ok=True)


def _register_all_blueprints(app: Flask) -> None:
    # 旧 HTML 页面层已删除：旧命名空间只剩策略页占位规则、说明书页与运行时健康接口，
    # 由 install_legacy_retirement 在启动期换成跳转/410 适配器；工作台是唯一的业务入口。
    register_legacy_blueprints(app)
    app.register_blueprint(workbench_bp)
    install_legacy_retirement(app)


def _register_exit_backup(app: Flask) -> None:
    # global 退出备份：_EXIT_BACKUP_MANAGER 赋值 + atexit 注册须在 BackupManager 构造后、return 前同一逻辑点；
    # conftest 依赖 _run_exit_backup / _EXIT_BACKUP_REGISTERED 模块级名字不改名。
    backup_manager = RuntimeExitBackupManager(app)

    global _EXIT_BACKUP_MANAGER, _EXIT_BACKUP_REGISTERED
    _EXIT_BACKUP_MANAGER = backup_manager

    if not _EXIT_BACKUP_REGISTERED and should_own_runtime_resources(bool(app.config.get("DEBUG", False))):
        atexit.register(_run_exit_backup)
        _EXIT_BACKUP_REGISTERED = True
    elif not _EXIT_BACKUP_REGISTERED:
        app.logger.info("开发重载父进程跳过注册退出自动备份。")


def create_app_core(
    *,
    ui_mode: str,
    enable_secret_key: bool,
    enable_security_headers: bool,
    enable_session_cookie_hardening: bool,
) -> Flask:
    cfg_class = resolve_config_class(_config_map)

    base_dir = runtime_base_dir(anchor_file=_default_anchor_file())
    static_dir = os.path.join(base_dir, "static")
    templates_dir = os.path.join(base_dir, "templates")

    app = Flask(__name__, static_folder=static_dir, template_folder=templates_dir)
    app.json = StrictJSONProvider(app)
    install_runtime_host(app, request_shutdown=request_runtime_server_shutdown)
    app.config.from_object(cfg_class)
    _apply_runtime_config(app, base_dir=base_dir)
    app.config["APP_UI_MODE"] = ui_mode
    if prepare_system_restore_startup(app):
        return app
    # 静态资源长缓存（配合 url_for('static', ...) 版本参数）；只在没配置时给默认值，配成 0 就是不缓存。
    static_max_age = app.config["SEND_FILE_MAX_AGE_DEFAULT"]
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 43200 if static_max_age is None else int(static_max_age)
    install_versioned_url_for(app, static_dir)

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

    _ensure_runtime_dirs(app)

    schema_path = os.path.abspath(os.path.join(base_dir, "schema.sql"))
    schema_started = time.perf_counter()
    launcher_log_warning(app.logger, "启动阶段 schema_begin pid=%s。", os.getpid(),
                         cfg_log_dir=app.config["LOG_DIR"], logger_level="info")
    ensure_schema(
        app.config["DATABASE_PATH"],
        app.logger,
        schema_path=schema_path if os.path.exists(schema_path) else None,
        backup_dir=app.config.get("BACKUP_DIR"),
    )
    launcher_log_warning(app.logger, "启动阶段 schema_complete pid=%s duration=%.3fs。",
                         os.getpid(), time.perf_counter() - schema_started,
                         cfg_log_dir=app.config["LOG_DIR"], logger_level="info")
    bootstrap_schedule_config(app.config["DATABASE_PATH"], logger=app.logger)

    plugin_status = bootstrap_plugins(
        base_dir,
        app.config["DATABASE_PATH"],
        logger=app.logger,
    )
    app.config["PLUGIN_STATUS"] = plugin_status

    install_workbench_request_lifecycle(app)

    @app.before_request
    def _open_db():
        g._aps_req_started = time.perf_counter()
        req_path = request.path
        # 白名单短路路径只允许走“无业务依赖”的轻量请求：
        # 不挂载 g.app_logger / g.db / g.op_logger，避免把静态资源与健康检查误带入请求级连接生命周期。
        # 若未来某个中间件需要这些请求级对象，则不应复用该白名单短路路径。
        if req_path.startswith("/static") or req_path in {"/system/health", "/system/runtime/shutdown"}:
            return
        maintenance_active = False
        maintenance_detection_error = None
        try:
            maintenance_active = bool(is_maintenance_window_active(app.config["DATABASE_PATH"], logger=app.logger))
        except Exception as e:
            maintenance_detection_error = e
        if maintenance_detection_error is not None:
            app.logger.error("系统状态检测失败，已中止请求：%s", maintenance_detection_error)
            return _maintenance_detection_failure_response()
        if maintenance_active:
            return _maintenance_gate_response()
        g.app_logger = current_app.logger

        if "db" not in g:
            conn = None
            try:
                conn = get_connection(app.config["DATABASE_PATH"])
                track_workbench_request_connection(conn)
                op_logger = OperationLogger(conn, logger=current_app.logger)
            except Exception:
                if conn is not None:
                    try:
                        close_workbench_request_connection(conn)
                    except Exception as close_exc:
                        _app_log_once(
                            app,
                            "request_scope_mount_close_failed",
                            "warning",
                            "请求级容器装配失败后的数据库关闭失败，已按清理型尽力而为继续：%s",
                            close_exc,
                        )
                raise

            g.db = conn
            g.op_logger = op_logger

    @app.teardown_appcontext
    def _close_db(_exc):
        db = g.pop("db", None)
        if db is not None:
            try:
                close_workbench_request_connection(db)
            except Exception as exc:
                _app_log_once(app, "close_db_failed", "warning", "数据库连接关闭失败，已按清理型尽力而为继续：%s", exc)

    if enable_security_headers:
        register_security_headers(app)

    @app.after_request
    def _schedule_idle_maintenance(resp):
        runtime = app.extensions.get("workbench_run_runtime")
        if (runtime is not None and runtime.ready and resp.status_code < 400
                and not request.path.startswith("/static/")
                and request.path not in {"/system/health", "/system/runtime/shutdown"}):
            call_on_workbench_request_close(runtime.request_maintenance_check)
        return resp

    @app.after_request
    def _perf_headers(resp):
        # 慢请求可观测：帮助区分“前端卡”与“后端慢”
        def _is_prefetch_req() -> bool:
            purpose = (request.headers.get("Purpose") or "").strip().lower()
            sec_purpose = (request.headers.get("Sec-Purpose") or "").strip().lower()
            x_moz = (request.headers.get("X-Moz") or "").strip().lower()
            return (
                "prefetch" in purpose
                or "prefetch" in sec_purpose
                or x_moz == "prefetch"
            )

        started = g.get("_aps_req_started")
        if started is not None:
            total_ms = int((time.perf_counter() - float(started)) * 1000)
            resp.headers.setdefault("Server-Timing", f"app;dur={total_ms}")
            req_path = request.path
            if total_ms >= 300 and not req_path.startswith("/static") and not _is_prefetch_req():
                app.logger.warning(f"慢请求: {request.method} {req_path} {total_ms}ms")
        return resp

    register_error_handlers(app)

    _register_all_blueprints(app)
    _register_exit_backup(app)

    if ui_mode == "new_ui":
        app.logger.info("应用启动完成 (UI Test Mode)。")
    else:
        app.logger.info("应用启动完成。")
    return app
