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
        "检测到非法 next 跳转参数，已忽略并回退到默认跳转：reason=%s raw=%r path=%s",
        str(reason or "unknown"),
        raw,
        path,
    )


def _safe_next_url_core(raw: Optional[str], *, url_for_fn=None) -> Optional[str]:
    """
    安全重定向：
    - 仅允许站内相对路径（禁止 http(s):// 或 //host 形式）
    - 兼容 request.full_path 末尾的 '?'（无查询时）
    - 空值返回 None，由调用方决定默认回跳
    - 非空非法值会记录 warning，并返回 None
    """
    s = (raw or "").strip()
    if not s:
        return None
    if s.endswith("?"):
        s = s[:-1]
    if s.startswith("//"):
        _warn_invalid_next_url_once(raw=raw, reason="protocol_relative")
        return None
    if any(ch in s for ch in ("\r", "\n", "\x00", "\\")):
        _warn_invalid_next_url_once(raw=raw, reason="control_or_backslash")
        return None
    try:
        p = urlparse(s)
        if p.scheme or p.netloc:
            _warn_invalid_next_url_once(raw=raw, reason="absolute_url")
            return None
    except Exception:
        _warn_invalid_next_url_once(raw=raw, reason="parse_failed")
        return None
    if not s.startswith("/"):
        s = "/" + s
    return s


def _safe_next_url(raw: Optional[str]) -> Optional[str]:
    return _safe_next_url_core(raw, url_for_fn=url_for)


def _same_origin_absolute_to_relative(raw: Optional[str]) -> Optional[str]:
    s = (raw or "").strip()
    if not s:
        return None

    try:
        parsed = urlparse(s)
    except Exception:
        return None

    if not parsed.scheme or not parsed.netloc:
        return None

    try:
        current = urlparse(str(request.host_url or ""))
    except Exception:
        return None

    if parsed.scheme != current.scheme or parsed.netloc != current.netloc:
        return None

    candidate = parsed.path or "/"
    if parsed.query:
        candidate = f"{candidate}?{parsed.query}"
    return _safe_next_url(candidate)
