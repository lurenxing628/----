from __future__ import annotations

import os
import secrets

from flask import Flask

from core.infrastructure.logging import safe_log
from core.infrastructure.safe_files import is_regular_file, read_fixed_text, write_fixed_text


def ensure_secret_key(app: Flask) -> None:
    """
    确保 SECRET_KEY：
    - 优先环境变量 SECRET_KEY
    - 否则读取 {LOG_DIR}/aps_secret_key.txt（若存在且长度足够）
    - 否则生成强随机并尽最大努力写入该文件（不阻断启动）
    """
    env_key = (os.environ.get("SECRET_KEY") or "").strip()
    if env_key:
        app.config["SECRET_KEY"] = env_key
        return

    secret_file = os.path.join(app.config["LOG_DIR"], "aps_secret_key.txt")
    min_len = 32

    try:
        # 拒绝软链接：与日志读取/诊断包同一道锁，挡「固定文件名指向任意文件」借壳；
        # 是软链接则跳过读取、走下方重新生成（诚实降级，不跟随链接读到非预期内容）。
        if is_regular_file(secret_file):
            key0 = read_fixed_text(secret_file).strip()
            if len(key0) >= min_len:
                app.config["SECRET_KEY"] = key0
                return
    except Exception as e:
        safe_log(app.logger, "warning", "读取 SECRET_KEY 文件失败（将尝试重新生成）：%s", e)

    key = secrets.token_urlsafe(32)
    app.config["SECRET_KEY"] = key

    try:
        write_fixed_text(secret_file, key + "\n", replace_symlink=True)
        app.logger.info("已生成 SECRET_KEY 并写入：%s", secret_file)
    except Exception as e:
        safe_log(app.logger, "warning", "写入 SECRET_KEY 文件失败（将使用进程内随机 SECRET_KEY）：%s", e)


def apply_session_cookie_hardening(app: Flask) -> None:
    # 不强制 secure，允许 HTTP 本地开发。
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


def register_security_headers(app: Flask) -> None:
    @app.after_request
    def _security_headers(resp):
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return resp
