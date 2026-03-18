import argparse
import atexit
import os
import secrets
import sys

from flask import Flask

from web.bootstrap.factory import create_app_core, serve_runtime_app, should_register_runtime_lifecycle_handlers
from web.bootstrap.launcher import (
    acquire_runtime_lock,
    clear_launch_error,
    current_runtime_owner,
    default_chrome_profile_dir,
    delete_runtime_contract_files,
    pick_bind_host,
    pick_port,
    release_runtime_lock,
    stop_runtime_from_dir,
    write_launch_error,
    write_runtime_contract_file,
    write_runtime_host_port_files,
)
from web.bootstrap.paths import runtime_base_dir


def _runtime_base_dir() -> str:
    return runtime_base_dir(anchor_file=__file__)


def _prelaunch_log_dir(runtime_dir: str) -> str:
    raw = str(os.environ.get("APS_LOG_DIR") or "").strip()
    if raw:
        return os.path.abspath(raw)
    return os.path.join(runtime_dir, "logs")


def create_app() -> Flask:
    # A06：new_ui 入口安全策略显式收敛到与主入口一致。
    return create_app_core(
        ui_mode="new_ui",
        enable_secret_key=True,
        enable_security_headers=True,
        enable_session_cookie_hardening=True,
    )


if __name__ != "__main__":
    app = create_app()


def _parse_cli_args(argv):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--runtime-stop", default="")
    parser.add_argument("--stop-aps-chrome", action="store_true")
    return parser.parse_known_args(argv)


def _configure_runtime_contract(app: Flask, runtime_dir: str, host: str, port: int, owner: str) -> None:
    shutdown_token = secrets.token_urlsafe(32)
    app.config["APS_RUNTIME_SHUTDOWN_TOKEN"] = shutdown_token
    app.config["APS_RUNTIME_DIR"] = runtime_dir
    app.config["APS_RUNTIME_OWNER"] = owner

    write_runtime_host_port_files(
        runtime_dir=runtime_dir,
        cfg_log_dir=app.config.get("LOG_DIR"),
        host=host,
        port=port,
        db_path=app.config.get("DATABASE_PATH"),
        logger=app.logger,
    )
    write_runtime_contract_file(
        runtime_dir,
        host,
        port,
        db_path=app.config.get("DATABASE_PATH"),
        shutdown_token=shutdown_token,
        ui_mode=str(app.config.get("APP_UI_MODE") or "new_ui"),
        log_dir=app.config.get("LOG_DIR"),
        backup_dir=app.config.get("BACKUP_DIR"),
        excel_template_dir=app.config.get("EXCEL_TEMPLATE_DIR"),
        exe_path=sys.executable,
        chrome_profile_dir=default_chrome_profile_dir(runtime_dir),
        owner=owner,
        logger=app.logger,
    )


def main(argv=None) -> int:
    args, _unknown = _parse_cli_args(argv or sys.argv[1:])
    if str(args.runtime_stop or "").strip():
        return int(
            stop_runtime_from_dir(
                str(args.runtime_stop).strip(),
                stop_aps_chrome=bool(args.stop_aps_chrome),
            )
        )

    runtime_dir = _runtime_base_dir()
    prelaunch_log_dir = _prelaunch_log_dir(runtime_dir)
    runtime_owner = current_runtime_owner()
    try:
        clear_launch_error(prelaunch_log_dir)
    except Exception:
        pass
    try:
        acquire_runtime_lock(
            runtime_dir,
            prelaunch_log_dir,
            owner=runtime_owner,
            exe_path=sys.executable,
        )
    except Exception as e:
        try:
            write_launch_error(runtime_dir, str(e), prelaunch_log_dir)
        except Exception:
            pass
        return 13
    atexit.register(release_runtime_lock, prelaunch_log_dir, os.getpid())

    try:
        app = create_app()
    except Exception as e:
        try:
            write_launch_error(runtime_dir, f"应用启动失败：{e}", prelaunch_log_dir)
        except Exception:
            pass
        return 14
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

    debug = bool(app.config.get("DEBUG", False))
    try:
        _configure_runtime_contract(app, runtime_dir, host, port, runtime_owner)
    except Exception as e:
        try:
            app.logger.error(f"写入运行时契约失败：{e}")
        except Exception:
            pass
        try:
            write_launch_error(runtime_dir, f"写入运行时契约失败：{e}", app.config.get("LOG_DIR"))
        except Exception:
            pass
        return 15
    if should_register_runtime_lifecycle_handlers(debug):
        atexit.register(delete_runtime_contract_files, app.config.get("LOG_DIR") or runtime_dir)

    use_reloader = debug and not getattr(sys, "frozen", False)
    if use_reloader:
        app.run(host=host, port=port, debug=debug, use_reloader=True)
        return 0
    serve_runtime_app(app, host, port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

