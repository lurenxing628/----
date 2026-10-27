from __future__ import annotations

from typing import Any, Optional
from urllib.parse import urlsplit

from flask import has_request_context, request


def _has_forbidden_manual_chars(text: str) -> bool:
    # 控制字符/反斜杠守卫（开放重定向防护核心）：必须在 urlsplit 之前对原始 text 调用。
    return any(ch in text for ch in ("\r", "\n", "\x00", "\\"))


def _is_same_origin(parsed: Any, current: Any) -> bool:
    # 空 scheme/netloc 先判否（短路），再比 scheme/netloc 相等——退化输入（无 scheme）不放行。
    return (
        bool(parsed.scheme)
        and bool(parsed.netloc)
        and parsed.scheme == current.scheme
        and parsed.netloc == current.netloc
    )


def _compose_same_origin_candidate(parsed: Any, text: str) -> str:
    # 末尾空问号依赖原始 text（urlsplit 会丢空 query 的 '?'），故须传入 text 而非只传 parsed。
    candidate = parsed.path or "/"
    if parsed.query:
        candidate = f"{candidate}?{parsed.query}"
    elif text.endswith("?"):
        candidate = f"{candidate}?"
    if parsed.fragment:
        candidate = f"{candidate}#{parsed.fragment}"
    return candidate


def normalize_manual_src_context(text: str) -> Optional[str]:
    if not text or text.startswith("//") or _has_forbidden_manual_chars(text):
        return None
    try:
        parsed = urlsplit(text)
    except ValueError:
        return None
    if parsed.path.startswith("//"):
        return None
    if not parsed.scheme and not parsed.netloc:
        return text if parsed.path.startswith("/") else None
    if not has_request_context():
        return None
    current = urlsplit(request.host_url)
    if not _is_same_origin(parsed, current):
        return None
    return _compose_same_origin_candidate(parsed, text)
