from __future__ import annotations

import os
import secrets

from flask import Flask


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

    log_dir = app.config.get("LOG_DIR") or ""
    try:
        log_dir = str(log_dir).strip()
    except Exception:
        log_dir = ""

    secret_file = os.path.join(log_dir, "aps_secret_key.txt") if log_dir else ""
    min_len = 32

    if secret_file:
        try:
            if os.path.isfile(secret_file):
                with open(secret_file, "r", encoding="utf-8") as f:
                    key0 = (f.read() or "").strip()
                if len(key0) >= min_len:
                    app.config["SECRET_KEY"] = key0
                    return
        except Exception as e:
            try:
                app.logger.warning(f"读取 SECRET_KEY 文件失败（将尝试重新生成）：{e}")
            except Exception:
                pass

    key = secrets.token_urlsafe(32)
    app.config["SECRET_KEY"] = key

    if not secret_file:
        return
    try:
        os.makedirs(log_dir, exist_ok=True)
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(key + "\n")
        try:
            app.logger.info(f"已生成 SECRET_KEY 并写入：{secret_file}")
        except Exception:
            pass
    except Exception as e:
        try:
            app.logger.warning(f"写入 SECRET_KEY 文件失败（将使用进程内随机 SECRET_KEY）：{e}")
        except Exception:
            pass


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

