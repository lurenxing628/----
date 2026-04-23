from __future__ import annotations

from typing import Any, Optional

from flask import current_app, flash, redirect, request, url_for

from core.infrastructure.logging import safe_log
from web.ui_mode import UI_MODE_CONFIG_KEY, UI_MODE_COOKIE_KEY, normalize_ui_mode

from .navigation_utils import _safe_next_url, _same_origin_absolute_to_relative
from .system_bp import bp
from .system_utils import _get_system_config_service


def _resolve_ui_mode_next_url(raw_next: Optional[str], raw_referrer: Optional[str]) -> str:
    next_url = _safe_next_url(raw_next)
    if next_url is None:
        next_url = _same_origin_absolute_to_relative(raw_referrer)
    if next_url is None:
        next_url = _safe_next_url(raw_referrer)
    if next_url is None:
        next_url = url_for("dashboard.index")
    return next_url


def _persist_ui_mode_db(svc: Any, mode: str) -> tuple[bool, Optional[str]]:
    try:
        svc.set_value(
            UI_MODE_CONFIG_KEY,
            mode,
            description="UI 模式：v1/v2（v2=新UI）",
        )
        return True, None
    except Exception as exc:
        error_text = str(exc)
        safe_log(current_app.logger, "warning", f"写入 UI 模式到 SystemConfig 失败（将仅使用 Cookie）：{exc}")
        return False, error_text


def _persist_ui_mode_cookie(resp: Any, mode: str) -> tuple[bool, Optional[str]]:
    try:
        resp.set_cookie(
            UI_MODE_COOKIE_KEY,
            mode,
            max_age=365 * 24 * 3600,
            path="/",
            samesite="Lax",
        )
        return True, None
    except Exception as exc:
        error_text = str(exc)
        safe_log(current_app.logger, "warning", f"写入 UI 模式 cookie 失败：{exc}")
        return False, error_text


def _flash_ui_mode_result(
    mode: str,
    db_ok: bool,
    cookie_ok: bool,
    db_error_text: Optional[str],
    cookie_error_text: Optional[str],
) -> None:
    mode_zh = "现代" if mode == "v2" else "经典"
    if db_ok and cookie_ok:
        flash(f"已切换界面：{mode_zh}。", "success")
    elif (not db_ok) and cookie_ok:
        flash(f"已切换界面：{mode_zh}，仅当前浏览器生效。", "warning")
    elif db_ok and (not cookie_ok):
        flash(f"已切换界面：{mode_zh}，全局默认已更新，但当前浏览器未写入 Cookie。", "warning")
    else:
        _ = db_error_text, cookie_error_text
        flash(f"切换界面失败：{mode_zh} 未保存。", "error")


@bp.post("/ui-mode")
def ui_mode_set():
    """
    UI 模式切换：
    - 写 Cookie（浏览器级）
    - 写 SystemConfig.ui_mode（全局默认；换浏览器也生效）
    """
    mode = normalize_ui_mode(request.form.get("mode"))
    next_url = _resolve_ui_mode_next_url(request.form.get("next"), request.referrer)
    if not mode:
        flash("UI 模式不合法（仅允许 v1/v2）。", "error")
        return redirect(next_url)

    svc = _get_system_config_service()
    resp = redirect(next_url)
    db_persisted, db_error_text = _persist_ui_mode_db(svc, mode)
    cookie_persisted, cookie_error_text = _persist_ui_mode_cookie(resp, mode)
    _flash_ui_mode_result(mode, db_persisted, cookie_persisted, db_error_text, cookie_error_text)
    return resp
