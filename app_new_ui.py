import os
import sys

from flask import Flask

from web.bootstrap.factory import create_app_core
from web.bootstrap.launcher import pick_bind_host, pick_port, write_runtime_host_port_files
from web.bootstrap.paths import runtime_base_dir


def _runtime_base_dir() -> str:
    return runtime_base_dir(anchor_file=__file__)


def create_app() -> Flask:
    # A06：new_ui 入口安全策略显式收敛到与主入口一致。
    return create_app_core(
        ui_mode="new_ui",
        enable_secret_key=True,
        enable_security_headers=True,
        enable_session_cookie_hardening=True,
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

