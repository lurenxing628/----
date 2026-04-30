from __future__ import annotations

from typing import Any, Optional

from flask import current_app, has_request_context, request

from core.infrastructure.logging import safe_log

UI_MODE_COOKIE_KEY = "aps_ui_mode"
# stored in SystemConfig
UI_MODE_CONFIG_KEY = "ui_mode"
DEFAULT_UI_MODE = "v2"
VALID_UI_MODES = ("v1", "v2")


def normalize_ui_mode(value: Any) -> Optional[str]:
    v = ("" if value is None else str(value)).strip().lower()
    return v if v in VALID_UI_MODES else None


def _current_logger():
    try:
        return current_app.logger
    except RuntimeError:
        return None


def _log_warning(message: str, *args: Any) -> None:
    safe_log(_current_logger(), "warning", message, *args)


def get_ui_mode(default: str = DEFAULT_UI_MODE) -> str:
    """
    获取当前 UI 模式：
    - Cookie 优先（浏览器级）
    - 其次 DB SystemConfig（全局默认）
    - 最后 default（兜底）
    """
    d = normalize_ui_mode(default) or DEFAULT_UI_MODE
    if not has_request_context():
        return d

    try:
        cookie_mode = normalize_ui_mode(request.cookies.get(UI_MODE_COOKIE_KEY))
        if cookie_mode:
            return cookie_mode
    except Exception as exc:
        _log_warning("读取 UI 模式 cookie 失败，已回退到数据库/默认值：%s", exc)

    from web.ui_mode_store import _read_ui_mode_from_db, _warn_invalid_db_ui_mode_once

    db_read = _read_ui_mode_from_db()
    if db_read.mode:
        return db_read.mode
    if not db_read.missing:
        _warn_invalid_db_ui_mode_once(db_read.invalid_raw_value)

    return d
