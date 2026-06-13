from __future__ import annotations

import os
import secrets

from flask import Flask

from core.infrastructure.logging import safe_log


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
    except Exception as e:
        log_dir = ""
        safe_log(
            getattr(app, "logger", None),
            "warning",
            "LOG_DIR 配置解析失败，SECRET_KEY 将仅保留进程内随机值：%s",
            e,
        )

    secret_file = os.path.join(log_dir, "aps_secret_key.txt") if log_dir else ""
    min_len = 32

    if secret_file:
        try:
            # 拒绝软链接：与日志读取/诊断包同一道锁，挡「固定文件名指向任意文件」借壳；
            # 是软链接则跳过读取、走下方重新生成（诚实降级，不跟随链接读到非预期内容）。
            if os.path.isfile(secret_file) and not os.path.islink(secret_file):
                with open(secret_file, encoding="utf-8") as f:
                    key0 = (f.read() or "").strip()
                if len(key0) >= min_len:
                    app.config["SECRET_KEY"] = key0
                    return
        except Exception as e:
            safe_log(getattr(app, "logger", None), "warning", "读取 SECRET_KEY 文件失败（将尝试重新生成）：%s", e)

    key = secrets.token_urlsafe(32)
    app.config["SECRET_KEY"] = key

    if not secret_file:
        return
    try:
        os.makedirs(log_dir, exist_ok=True)
        # 不跟随软链接写入：secret_file 是软链接时 open(..,"w") 会写穿到链接目标、覆盖任意文件
        # （finding-01 写侧补齐——读侧已 islink 跳过，写侧同样不能跟随）。写前移除软链接本身
        # （os.remove 删链接不删目标），确保创建的是 log_dir 下真实普通文件。
        if os.path.islink(secret_file):
            os.remove(secret_file)
        with open(secret_file, "w", encoding="utf-8") as f:
            f.write(key + "\n")
        safe_log(getattr(app, "logger", None), "info", "已生成 SECRET_KEY 并写入：%s", secret_file)
    except Exception as e:
        safe_log(getattr(app, "logger", None), "warning", "写入 SECRET_KEY 文件失败（将使用进程内随机 SECRET_KEY）：%s", e)


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

