from __future__ import annotations

from typing import Optional
from urllib.parse import urlparse

from flask import current_app, g, request, url_for

from core.infrastructure.logging import safe_log


def _warn_invalid_next_url_once(*, raw: Optional[str], reason: str) -> None:
    warned = bool(getattr(g, "_aps_invalid_next_url_warned", False))
    if warned:
        return
    g._aps_invalid_next_url_warned = True
    path = str(request.path or "")
    safe_log(
        current_app.logger,
        "warning",
        "检测到非法 next 跳转参数，已回退到首页：reason=%s raw=%r path=%s",
        str(reason or "unknown"),
        raw,
        path,
    )


def _safe_next_url_core(raw: Optional[str], *, url_for_fn) -> str:
    """
    安全重定向：
    - 仅允许站内相对路径（禁止 http(s):// 或 //host 形式）
    - 兼容 request.full_path 末尾的 '?'（无查询时）
    - 空值统一回退到 dashboard 首页；非空非法值会记录 warning 后回退
    """
    s = (raw or "").strip()
    if not s:
        return url_for_fn("dashboard.index")
    if s.endswith("?"):
        s = s[:-1]
    if s.startswith("//"):
        _warn_invalid_next_url_once(raw=raw, reason="protocol_relative")
        return url_for_fn("dashboard.index")
    if any(ch in s for ch in ("\r", "\n", "\x00", "\\")):
        _warn_invalid_next_url_once(raw=raw, reason="control_or_backslash")
        return url_for_fn("dashboard.index")
    try:
        p = urlparse(s)
        if p.scheme or p.netloc:
            _warn_invalid_next_url_once(raw=raw, reason="absolute_url")
            return url_for_fn("dashboard.index")
    except Exception:
        _warn_invalid_next_url_once(raw=raw, reason="parse_failed")
        return url_for_fn("dashboard.index")
    if not s.startswith("/"):
        s = "/" + s
    return s


def _safe_next_url(raw: Optional[str]) -> str:
    return _safe_next_url_core(raw, url_for_fn=url_for)
