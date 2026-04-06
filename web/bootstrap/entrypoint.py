from __future__ import annotations

import argparse
import os
import secrets
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from flask import Flask

from .factory import (
    create_app_core,
    serve_runtime_app,
    should_own_runtime_resources,
    should_register_runtime_lifecycle_handlers,
    should_use_runtime_reloader,
)
from .launcher import (
    acquire_runtime_lock,
    clear_launch_error,
    current_runtime_owner,
    default_chrome_profile_dir,
    delete_runtime_contract_files,
    pick_bind_host,
    pick_port,
    release_runtime_lock,
    resolve_prelaunch_log_dir,
    stop_runtime_from_dir,
    write_launch_error,
    write_runtime_contract_file,
    write_runtime_host_port_files,
)
from .paths import runtime_base_dir


@dataclass(frozen=True)
class EntryPointDeps:
    create_app: Callable[[], Flask]
    clear_launch_error: Callable[..., Any]
    write_launch_error: Callable[..., Any]
    current_runtime_owner: Callable[[], str]
    resolve_prelaunch_log_dir: Callable[[str], str]
    acquire_runtime_lock: Callable[..., Any]
    release_runtime_lock: Callable[..., Any]
    delete_runtime_contract_files: Callable[..., Any]
    write_runtime_host_port_files: Callable[..., Any]
    write_runtime_contract_file: Callable[..., Any]
    default_chrome_profile_dir: Callable[[str], str]
    pick_bind_host: Callable[..., str]
    pick_port: Callable[..., Any]
    stop_runtime_from_dir: Callable[..., int]
    serve_runtime_app: Callable[[Flask, str, int], Any]
    should_use_runtime_reloader: Callable[[bool], bool]
    should_own_runtime_resources: Callable[[bool], bool]
    should_register_runtime_lifecycle_handlers: Callable[[bool], bool]
    atexit_register: Callable[..., Any]


def create_app_with_mode(ui_mode: str = "default") -> Flask:
    return create_app_core(
        ui_mode=ui_mode,
        enable_secret_key=True,
        enable_security_headers=True,
        enable_session_cookie_hardening=True,
    )


def _parse_cli_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime-stop", default="")
    parser.add_argument("--stop-aps-chrome", action="store_true")
    return parser.parse_known_args(argv)


def _default_deps(ui_mode: str) -> EntryPointDeps:
    return EntryPointDeps(
        create_app=lambda: create_app_with_mode(ui_mode),
        clear_launch_error=clear_launch_error,
        write_launch_error=write_launch_error,
        current_runtime_owner=current_runtime_owner,
        resolve_prelaunch_log_dir=resolve_prelaunch_log_dir,
        acquire_runtime_lock=acquire_runtime_lock,
        release_runtime_lock=release_runtime_lock,
        delete_runtime_contract_files=delete_runtime_contract_files,
        write_runtime_host_port_files=write_runtime_host_port_files,
        write_runtime_contract_file=write_runtime_contract_file,
        default_chrome_profile_dir=default_chrome_profile_dir,
        pick_bind_host=pick_bind_host,
        pick_port=pick_port,
        stop_runtime_from_dir=stop_runtime_from_dir,
        serve_runtime_app=serve_runtime_app,
        should_use_runtime_reloader=should_use_runtime_reloader,
        should_own_runtime_resources=should_own_runtime_resources,
        should_register_runtime_lifecycle_handlers=should_register_runtime_lifecycle_handlers,
        atexit_register=__import__("atexit").register,
    )


def configure_runtime_contract(
    app: Flask,
    runtime_dir: str,
    host: str,
    port: int,
    owner: str,
    *,
    default_ui_mode: str,
    deps: EntryPointDeps,
) -> None:
    shutdown_token = secrets.token_urlsafe(32)
    app.config["APS_RUNTIME_SHUTDOWN_TOKEN"] = shutdown_token
    app.config["APS_RUNTIME_DIR"] = runtime_dir
    app.config["APS_RUNTIME_OWNER"] = owner

    deps.write_runtime_host_port_files(
        runtime_dir=runtime_dir,
        cfg_log_dir=app.config.get("LOG_DIR"),
        host=host,
        port=port,
        db_path=app.config.get("DATABASE_PATH"),
        logger=app.logger,
    )
    deps.write_runtime_contract_file(
        runtime_dir,
        host,
        port,
        db_path=app.config.get("DATABASE_PATH"),
        shutdown_token=shutdown_token,
        ui_mode=str(app.config.get("APP_UI_MODE") or default_ui_mode),
        log_dir=app.config.get("LOG_DIR"),
        backup_dir=app.config.get("BACKUP_DIR"),
        excel_template_dir=app.config.get("EXCEL_TEMPLATE_DIR"),
        exe_path=sys.executable,
        chrome_profile_dir=deps.default_chrome_profile_dir(runtime_dir),
        owner=owner,
        logger=app.logger,
    )


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
    if str(args.runtime_stop or "").strip():
        return int(
            deps.stop_runtime_from_dir(
                str(args.runtime_stop).strip(),
                stop_aps_chrome=bool(args.stop_aps_chrome),
            )
        )

    runtime_dir = runtime_base_dir(anchor_file=anchor_file)
    prelaunch_log_dir = deps.resolve_prelaunch_log_dir(runtime_dir)
    runtime_owner = deps.current_runtime_owner()
    try:
        deps.clear_launch_error(prelaunch_log_dir)
    except Exception:
        pass

    try:
        app = deps.create_app()
    except Exception as e:
        try:
            deps.write_launch_error(runtime_dir, f"应用启动失败：{e}", prelaunch_log_dir)
        except Exception:
            pass
        return 14
    debug = bool(app.config.get("DEBUG", False))
    use_reloader = deps.should_use_runtime_reloader(debug)
    owns_runtime_resources = deps.should_own_runtime_resources(debug)

    raw_host = os.environ.get("APS_HOST")
    host = deps.pick_bind_host(raw_host, logger=app.logger)

    raw_port = os.environ.get("APS_PORT")
    preferred_port = 5000
    if raw_port is not None and str(raw_port).strip() != "":
        try:
            preferred_port = int(str(raw_port).strip())
        except Exception:
            preferred_port = 5000

    requested_host = host
    host, port = deps.pick_port(host, preferred_port, logger=app.logger)
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

    if owns_runtime_resources:
        try:
            deps.acquire_runtime_lock(
                runtime_dir,
                prelaunch_log_dir,
                owner=runtime_owner,
                exe_path=sys.executable,
            )
        except Exception as e:
            try:
                deps.write_launch_error(runtime_dir, str(e), prelaunch_log_dir)
            except Exception:
                pass
            return 13
        deps.atexit_register(deps.release_runtime_lock, prelaunch_log_dir, os.getpid())

        try:
            configure_runtime_contract(
                app,
                runtime_dir,
                host,
                port,
                runtime_owner,
                default_ui_mode=ui_mode,
                deps=deps,
            )
        except Exception as e:
            try:
                app.logger.error(f"写入运行时契约失败：{e}")
            except Exception:
                pass
            try:
                deps.write_launch_error(runtime_dir, f"写入运行时契约失败：{e}", app.config.get("LOG_DIR"))
            except Exception:
                pass
            return 15
        if deps.should_register_runtime_lifecycle_handlers(debug):
            deps.atexit_register(deps.delete_runtime_contract_files, app.config.get("LOG_DIR") or runtime_dir)
    else:
        try:
            app.logger.info("开发重载父进程跳过获取运行时锁与运行时契约。")
        except Exception:
            pass

    if use_reloader:
        app.run(host=host, port=port, debug=debug, use_reloader=True)
        return 0
    deps.serve_runtime_app(app, host, port)
    return 0
