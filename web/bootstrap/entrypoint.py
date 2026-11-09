from __future__ import annotations

import argparse
import os
import secrets
import signal
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from flask import Flask

from core.infrastructure.logging import safe_log
from web.runtime_host import runtime_identity

from . import factory as _factory
from .factory import (
    create_app_core,
    resolve_startup_debug_flag,
    serve_runtime_app,
    should_own_runtime_resources,
    should_use_runtime_reloader,
)
from .launcher_cleanup_result import delete_runtime_contract_files_result
from .launcher_contracts import (
    clear_launch_error,
    write_runtime_contract_file,
)
from .launcher_network import pick_bind_host
from .launcher_observability import launcher_log_warning
from .launcher_paths import (
    current_runtime_owner,
    default_chrome_profile_dir,
    resolve_prelaunch_log_dir,
    resolve_runtime_db_path,
)
from .launcher_runtime_lock import acquire_runtime_lock, release_runtime_lock
from .launcher_stop import stop_runtime_from_dir
from .paths import runtime_base_dir
from .runtime_server import prepare_runtime_server
from .workbench_run_lifecycle import install_run_lifecycle, release_runtime_after_jobs, stop_run_runtime
from .workbench_system_restore_recovery import RECOVERY

PUBLIC_LAUNCH_ERROR_MESSAGE = "应用启动失败：程序没有正常启动，请把 launcher.log 发给维护人员排查。"


@dataclass(frozen=True)
class EntryPointDeps:
    create_app: Callable[[], Flask]
    clear_launch_error: Callable[..., Any]
    current_runtime_owner: Callable[[], str]
    resolve_prelaunch_log_dir: Callable[[str], str]
    acquire_runtime_lock: Callable[..., Any]
    release_runtime_lock: Callable[..., Any]
    delete_runtime_contract_files: Callable[..., Any]
    write_runtime_contract_file: Callable[..., Any]
    default_chrome_profile_dir: Callable[[str], str]
    pick_bind_host: Callable[..., str]
    stop_runtime_from_dir: Callable[..., int]
    serve_runtime_app: Callable[..., Any]
    should_use_runtime_reloader: Callable[[bool], bool]
    should_own_runtime_resources: Callable[[bool], bool]
    install_run_runtime: Callable[..., Any]
    # 锁先于 create_app 的归属判定所需（app 尚不存在时解析 DEBUG）。
    resolve_startup_debug_flag: Callable[[], bool]
    # B03 锁命名空间与 DB 绑定：db-scope 锁所需的 DB 路径解析（与 factory._apply_runtime_config
    # 同源，合同测试锁定）。
    resolve_runtime_db_path: Callable[[str], str]
    # 预先占住监听端口并作为唯一监听端点事实源。
    prepare_runtime_server: Callable[..., Any]


def create_app_with_mode(ui_mode: str = "default") -> Flask:
    return create_app_core(ui_mode=ui_mode)


def _parse_cli_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime-stop", default="")
    parser.add_argument("--stop-aps-chrome", action="store_true")
    parser.add_argument("--sample-inject", action="store_true")
    return parser.parse_known_args(argv)


def _default_deps(ui_mode: str) -> EntryPointDeps:
    from .workbench_run_runtime import install_workbench_run_runtime

    return EntryPointDeps(
        create_app=lambda: create_app_with_mode(ui_mode),
        clear_launch_error=clear_launch_error,
        current_runtime_owner=current_runtime_owner,
        resolve_prelaunch_log_dir=resolve_prelaunch_log_dir,
        acquire_runtime_lock=acquire_runtime_lock,
        release_runtime_lock=release_runtime_lock,
        delete_runtime_contract_files=delete_runtime_contract_files_result,
        write_runtime_contract_file=write_runtime_contract_file,
        default_chrome_profile_dir=default_chrome_profile_dir,
        pick_bind_host=pick_bind_host,
        stop_runtime_from_dir=stop_runtime_from_dir,
        serve_runtime_app=serve_runtime_app,
        should_use_runtime_reloader=should_use_runtime_reloader,
        should_own_runtime_resources=should_own_runtime_resources,
        resolve_startup_debug_flag=resolve_startup_debug_flag,
        resolve_runtime_db_path=resolve_runtime_db_path,
        install_run_runtime=install_workbench_run_runtime,
        prepare_runtime_server=prepare_runtime_server,
    )


def _write_launch_error_with_observability(
    runtime_dir: str,
    message: str,
    log_dir: Optional[str],
    *,
    logger,
    context: str,
) -> None:
    public_message = PUBLIC_LAUNCH_ERROR_MESSAGE
    result = launcher_log_warning(
        logger,
        "%s：%s",
        context,
        message,
        runtime_dir=runtime_dir,
        state_dir=log_dir,
        write_launch_error=True,
        logger_level="error",
        public_launch_error_message=public_message,
    )
    if not result.file_ok:
        return
    if not result.error_file_ok:
        launcher_log_warning(
            logger,
            "写入启动错误提示文件失败。",
            runtime_dir=runtime_dir,
            state_dir=log_dir,
            write_launch_error=False,
            logger_level="error",
        )


def configure_runtime_contract(
    app: Flask,
    runtime_dir: str,
    host: str,
    port: int,
    owner: str,
    *,
    deps: EntryPointDeps,
    runtime_lock: Dict[str, Any],
) -> Dict[str, Any]:
    shutdown_token = secrets.token_urlsafe(32)
    app.config["APS_RUNTIME_SHUTDOWN_TOKEN"] = shutdown_token
    app.config["APS_RUNTIME_DIR"] = runtime_dir
    app.config["APS_RUNTIME_OWNER"] = owner
    identity = runtime_identity(app)

    return deps.write_runtime_contract_file(
        runtime_dir,
        host,
        port,
        db_path=app.config.get("DATABASE_PATH"),
        shutdown_token=shutdown_token,
        instance_id=identity["instance_id"],
        ui_mode=app.config["APP_UI_MODE"],
        log_dir=app.config.get("LOG_DIR"),
        backup_dir=app.config.get("BACKUP_DIR"),
        excel_template_dir=app.config.get("EXCEL_TEMPLATE_DIR"),
        exe_path=sys.executable,
        chrome_profile_dir=deps.default_chrome_profile_dir(runtime_dir),
        owner=owner,
        logger=app.logger,
        expected_lock=runtime_lock,
    )


def _supervise_reloader() -> int:
    from werkzeug._reloader import reloader_loops

    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    reloader = reloader_loops["auto"]()
    try:
        return int(reloader.restart_with_reloader())
    except (KeyboardInterrupt, SystemExit):
        return 0


def app_main(
    ui_mode: str = "default",
    *,
    anchor_file: str,
    argv=None,
    deps: Optional[EntryPointDeps] = None,
) -> int:
    if deps is None:
        deps = _default_deps(ui_mode)

    args, _unknown = _parse_cli_args(argv or sys.argv[1:])
    runtime_stop = args.runtime_stop.strip()
    if runtime_stop:
        return int(deps.stop_runtime_from_dir(runtime_stop, stop_aps_chrome=bool(args.stop_aps_chrome)))

    runtime_dir = runtime_base_dir(anchor_file=anchor_file)
    if args.sample_inject:
        from .sample_injection import main as inject_complex_sample

        return int(inject_complex_sample(runtime_dir))

    # 开发重载父进程在触库、写秘密、注册备份、拿锁、绑定端口之前直接进入 reloader 监督。
    startup_debug = bool(deps.resolve_startup_debug_flag())
    if not deps.should_own_runtime_resources(startup_debug):
        return _supervise_reloader()

    prelaunch_log_dir = deps.resolve_prelaunch_log_dir(runtime_dir)
    is_frozen = bool(getattr(sys, "frozen", False))
    # 源码运行时，对外 contract 固定发布到 runtime_dir/logs；lock 也要收敛到同一命名空间，
    # 否则不同 APS_LOG_DIR 的实例会并发覆盖同一份 repo-root runtime contract。
    lock_scope_target = prelaunch_log_dir if is_frozen else runtime_dir
    lock_scope_log_dir = prelaunch_log_dir if is_frozen else None
    runtime_owner = deps.current_runtime_owner()
    deps.clear_launch_error(prelaunch_log_dir)

    # 双开防线：运行时锁必须先于 create_app 的一切共享库副作用（ensure_schema 迁移、退出备份注册）。
    # 锁被占的第二实例在触库前即退出（rc=13）——不会在运行实例底下迁移 schema，也不会挂上退出备份。
    runtime_lock_state: Dict[str, Any] = {}
    rc = _acquire_runtime_lock_before_app(
        deps,
        runtime_dir=runtime_dir,
        lock_scope_target=lock_scope_target,
        lock_scope_log_dir=lock_scope_log_dir,
        runtime_owner=runtime_owner,
        prelaunch_log_dir=prelaunch_log_dir,
        runtime_lock_state=runtime_lock_state,
    )
    if rc is not None:
        return rc

    app = None
    try:
        try:
            app = deps.create_app()
        except Exception as e:
            _write_launch_error_with_observability(
                runtime_dir, str(e), prelaunch_log_dir, logger=None, context="应用启动失败"
            )
            return 14
        return _serve_created_app(
            deps,
            app,
            runtime_dir=runtime_dir,
            lock_scope_target=lock_scope_target,
            prelaunch_log_dir=prelaunch_log_dir,
            runtime_owner=runtime_owner,
            runtime_lock_state=runtime_lock_state,
        )
    finally:
        # 拿锁成功后的唯一停机入口：app 未建成时只需释锁，建成后由 _serve_created_app 的 finally 收尾。
        if app is None:
            release_runtime_after_jobs(deps, runtime_lock_state, lock_scope_target)


def _serve_created_app(
    deps: EntryPointDeps,
    app: Flask,
    *,
    runtime_dir: str,
    lock_scope_target: str,
    prelaunch_log_dir: str,
    runtime_owner: str,
    runtime_lock_state: Dict[str, Any],
) -> int:
    debug = bool(app.config.get("DEBUG", False))
    prepared_server = None
    try:
        try:
            runtime_started = time.perf_counter()
            launcher_log_warning(
                app.logger,
                "启动阶段 runtime_recovery_begin pid=%s。",
                os.getpid(),
                cfg_log_dir=app.config["LOG_DIR"],
                logger_level="info",
            )
            install_run_lifecycle(deps, app, runtime_lock_state)
            launcher_log_warning(
                app.logger,
                "启动阶段 runtime_recovery_complete pid=%s duration=%.3fs。",
                os.getpid(),
                time.perf_counter() - runtime_started,
                cfg_log_dir=app.config["LOG_DIR"],
                logger_level="info",
            )
        except Exception as exc:
            _write_launch_error_with_observability(
                runtime_dir,
                str(exc),
                prelaunch_log_dir,
                logger=app.logger,
                context="排产运行恢复检查失败",
            )
            return 14

        use_reloader = (
            deps.should_use_runtime_reloader(debug)
            and app.config.get("WORKBENCH_RUN_RUNTIME_REASON") != RECOVERY
        )
        raw_host = os.environ.get("APS_HOST")
        requested_host = deps.pick_bind_host(raw_host, logger=app.logger)
        try:
            prepared_server = deps.prepare_runtime_server(
                app, requested_host, _preferred_listen_port(logger=app.logger)
            )
            host, port = prepared_server.server_address[:2]
        except Exception as exc:
            _write_launch_error_with_observability(
                runtime_dir,
                str(exc),
                prelaunch_log_dir,
                logger=app.logger,
                context="监听端口绑定失败",
            )
            return 16
        if host != requested_host:
            safe_log(
                app.logger,
                "warning",
                "APS_HOST=%s 不可绑定，已回退到 %s（port=%s）",
                requested_host,
                host,
                port,
            )
        _writeback_listen_env(host, port)

        rc = _publish_runtime_contract(
            deps,
            app,
            runtime_dir=runtime_dir,
            host=host,
            port=port,
            runtime_owner=runtime_owner,
            lock_state=runtime_lock_state,
        )
        if rc is not None:
            return rc

        if use_reloader:
            return _serve_with_reloader(deps, prepared_server=prepared_server)
        deps.serve_runtime_app(server=prepared_server)
        return 0
    finally:
        # 唯一停机顺序：关监听 → 排空请求与后台作业 → 退出备份 → 删契约 → 释锁。
        try:
            if prepared_server is not None:
                prepared_server.server_close()
        finally:
            try:
                stop_run_runtime(runtime_lock_state.get("runtime"))
                _factory.run_exit_backup_now()
            finally:
                release_runtime_after_jobs(deps, runtime_lock_state, lock_scope_target)


def _watch_reloader(reloader: Any, prepared_server: Any, reload_requested: threading.Event) -> None:
    try:
        reloader.run()
    except SystemExit as exc:
        if exc.code == 3:
            reload_requested.set()
            prepared_server.shutdown()


def _serve_with_reloader(
    deps: EntryPointDeps,
    *,
    prepared_server: Any,
) -> int:
    from werkzeug._reloader import ensure_echo_on, reloader_loops

    signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
    ensure_echo_on()
    reloader = reloader_loops["auto"]()
    reload_requested = threading.Event()
    with reloader:
        watcher = threading.Thread(
            target=_watch_reloader,
            args=(reloader, prepared_server, reload_requested),
            name="aps-reloader",
            daemon=True,
        )
        watcher.start()
        try:
            deps.serve_runtime_app(server=prepared_server)
        except (KeyboardInterrupt, SystemExit):
            return 0
    return 3 if reload_requested.is_set() else 0


def _preferred_listen_port(*, logger) -> int:
    raw_port = os.environ.get("APS_PORT")
    preferred_port = 5000
    if raw_port is not None and str(raw_port).strip() != "":
        try:
            preferred_port = int(str(raw_port).strip())
        except ValueError as exc:
            preferred_port = 5000
            safe_log(logger, "warning", "APS_PORT=%r 非法，已回退到默认候选端口 5000：%s", raw_port, exc)
    return preferred_port


def _writeback_listen_env(host, port) -> None:
    # 必须留 entrypoint 模块且走模块 os.environ（测试 monkeypatch entrypoint_mod.os.environ），禁子函数内 import os。
    os.environ["APS_HOST"] = str(host)
    os.environ["APS_PORT"] = str(port)


def _acquire_runtime_lock_before_app(
    deps,
    *,
    runtime_dir,
    lock_scope_target,
    lock_scope_log_dir,
    runtime_owner,
    prelaunch_log_dir,
    runtime_lock_state: Dict[str, Any],
) -> Optional[int]:
    # 副作用时序：acquire_lock → create_app（迁移/退出备份注册）→ 发布并保存契约身份；停机清理全部由
    # app_main / _serve_created_app 的 finally 承担。锁必须是第一个共享资源副作用（双开防线）。
    # 返回 None=成功继续；13=锁失败。此时 app 尚未创建，观测通道只有启动错误文件与 launcher.log（logger=None）。
    # B03：壳锁命名空间锚定日志目录（bat/stop 读取端合同），与 DB 的 env 锚点（APS_DB_PATH/shared-data root）
    # 可被分叉——同库双开的真互斥由 acquire_runtime_lock(db_path=...) 在 DB 同路径追加的 db-scope 锁承担；
    # db 路径解析必须与 factory._apply_runtime_config 同源（resolve_runtime_db_path，合同测试锁定）。
    try:
        runtime_db_path = deps.resolve_runtime_db_path(runtime_dir)
        acquired = deps.acquire_runtime_lock(
            lock_scope_target,
            lock_scope_log_dir,
            owner=runtime_owner,
            exe_path=sys.executable,
            db_path=runtime_db_path,
        )
    except Exception as e:
        _write_launch_error_with_observability(
            runtime_dir, str(e), prelaunch_log_dir, logger=None, context="获取运行时锁失败"
        )
        return 13
    runtime_lock_state["payload"] = acquired
    return None


def _publish_runtime_contract(
    deps,
    app,
    *,
    runtime_dir,
    host,
    port,
    runtime_owner,
    lock_state: Dict[str, Any],
) -> Optional[int]:
    # 契约失败用 app.logger（区别于锁/create_app 失败用 None），文案不统一化。返回 None=成功继续；15=契约失败。
    try:
        publication = configure_runtime_contract(
            app,
            runtime_dir,
            host,
            port,
            runtime_owner,
            deps=deps,
            runtime_lock=lock_state["payload"],
        )
        lock_state["contract"] = publication["payload"]
    except Exception as e:
        _write_launch_error_with_observability(
            runtime_dir, str(e), app.config.get("LOG_DIR"), logger=app.logger, context="写入运行时契约失败"
        )
        return 15
    # 停机 finally 在退出备份之后按这里记录的目录删除契约。
    lock_state["contract_cleanup_dir"] = os.path.dirname(publication["path"])
    return None
