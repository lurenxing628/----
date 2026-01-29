from __future__ import annotations

from flask import current_app, flash, g, redirect, request

from web.ui_mode import UI_MODE_COOKIE_KEY, UI_MODE_CONFIG_KEY, normalize_ui_mode

from core.infrastructure.transaction import TransactionManager
from data.repositories import SystemConfigRepository

from .system_bp import bp
from .system_utils import _safe_next_url


@bp.post("/ui-mode")
def ui_mode_set():
    """
    UI 模式切换：
    - 写 Cookie（浏览器级）
    - 写 SystemConfig.ui_mode（全局默认；换浏览器也生效）
    """
    mode = normalize_ui_mode(request.form.get("mode"))
    next_url = _safe_next_url(request.form.get("next") or request.referrer)
    if not mode:
        flash("UI 模式不合法（仅允许 v1/v2）。", "error")
        return redirect(next_url)

    # 1) DB 持久化（失败不阻断，仍可通过 cookie 生效）
    try:
        repo = SystemConfigRepository(g.db, logger=current_app.logger)
        with TransactionManager(g.db).transaction():
            repo.set(UI_MODE_CONFIG_KEY, mode, description="UI 模式：v1/v2（v2=新UI）")
    except Exception as e:
        try:
            current_app.logger.warning(f"写入 UI 模式到 SystemConfig 失败（将仅使用 Cookie）：{e}")
        except Exception:
            pass

    # 2) Cookie
    resp = redirect(next_url)
    try:
        resp.set_cookie(
            UI_MODE_COOKIE_KEY,
            mode,
            max_age=365 * 24 * 3600,
            path="/",
            samesite="Lax",
        )
    except Exception:
        pass

    mode_zh = "现代" if mode == "v2" else "经典"
    flash(f"已切换界面：{mode_zh}。", "success")
    return resp

