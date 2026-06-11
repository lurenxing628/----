from __future__ import annotations

from typing import Any, Dict, Optional
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import current_app, g, has_request_context, request, url_for
from werkzeug.routing.exceptions import BuildError

from core.infrastructure.logging import safe_log
from core.models.schedule_plan_role import VALID_PLAN_ROLES
from web.viewmodels.page_manuals import build_manual_for_endpoint, resolve_manual_id


def _log_warning(message: str, *args: Any) -> None:
    # 原住 web/ui_mode_request.py，双轨退役随其删除而内化到本模块（唯一存量消费方）
    try:
        logger = current_app.logger
    except RuntimeError:
        logger = None
    safe_log(logger, "warning", message, *args)


def _resolve_manual_endpoint(endpoint: Any = None) -> str:
    if endpoint is not None:
        return str(endpoint).strip()
    if not has_request_context():
        return ""
    try:
        return str(request.endpoint or "").strip()
    except Exception as exc:
        _log_warning("读取当前 endpoint 失败，已按无说明入口处理：%s", exc)
        return ""


def _normalize_relative_manual_src(text: str) -> Optional[str]:
    if not text or not text.startswith("/") or text.startswith("//"):
        return None
    if any(ch in text for ch in ("\r", "\n", "\x00", "\\")):
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    if parts.scheme or parts.netloc or not parts.path.startswith("/"):
        return None
    return text


def _same_origin_absolute_manual_src(raw: Any = None) -> Optional[str]:
    if not has_request_context():
        return None
    text = ("" if raw is None else str(raw)).strip()
    if not text or any(ch in text for ch in ("\r", "\n", "\x00", "\\")):
        return None
    try:
        parsed = urlsplit(text)
        current = urlsplit(str(request.host_url or ""))
    except ValueError:
        return None
    if not parsed.scheme or not parsed.netloc:
        return None
    if parsed.scheme != current.scheme or parsed.netloc != current.netloc:
        return None

    candidate = parsed.path or "/"
    if parsed.query:
        candidate = f"{candidate}?{parsed.query}"
    elif text.endswith("?"):
        candidate = f"{candidate}?"
    if parsed.fragment:
        candidate = f"{candidate}#{parsed.fragment}"
    return _normalize_relative_manual_src(candidate)


def normalize_manual_src(raw: Any = None) -> Optional[str]:
    text = ("" if raw is None else str(raw)).strip()
    return _normalize_relative_manual_src(text) or _same_origin_absolute_manual_src(text)


def _resolve_manual_src(src: Any = None) -> str:
    if src is not None:
        return str(src)
    if not has_request_context():
        return "/"
    try:
        full_path = getattr(request, "full_path", "") or ""
        if full_path:
            return str(full_path)
    except Exception as exc:
        _log_warning("读取当前请求完整路径失败，已尝试 path 回退：%s", exc)
    try:
        return str(getattr(request, "path", "") or "/")
    except Exception as exc:
        _log_warning("读取当前请求 path 失败，已回退到根路径：%s", exc)
        return "/"


def _sanitize_manual_src_context(src: Optional[str]) -> Optional[str]:
    if not src:
        return src
    try:
        parts = urlsplit(src)
    except ValueError:
        return src
    query = []
    changed = False
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key == "plan_role" and str(value or "").strip() not in VALID_PLAN_ROLES:
            changed = True
            continue
        query.append((key, value))
    if not changed:
        return src
    return urlunsplit(("", "", parts.path or "/", urlencode(query), parts.fragment))


def normalize_manual_src_context(raw: Any = None) -> Optional[str]:
    return _sanitize_manual_src_context(normalize_manual_src(raw))


def safe_url_for(endpoint: str, **values: Any) -> Optional[str]:
    """
    url_for 的安全封装：
    - endpoint 不存在（BuildError）时返回 None（而不是抛异常导致整页 500）
    - 其他异常记录 warning 后返回 None（保持页面可用，便于排障/渐进发布）
    """
    if not has_request_context():
        return None
    try:
        return url_for(endpoint, **values)
    except BuildError:
        try:
            logged = getattr(g, "_safe_url_for_missing_eps", None)
            if logged is None:
                logged = set()
                g._safe_url_for_missing_eps = logged
            if endpoint not in logged:
                logged.add(endpoint)
                path = ""
                try:
                    path = getattr(request, "path", "") or ""
                except Exception as exc:
                    path = ""
                    _log_warning("读取当前请求 path 失败，仍会记录缺失 endpoint：%s", exc)
                _log_warning(
                    "模板链接不可用：endpoint 未注册（%s），path=%s。可能原因：运行旧版本/未重启/未重新打包。",
                    endpoint,
                    path,
                )
        except Exception as exc:
            _log_warning("记录缺失 endpoint 告警失败，已保持页面继续渲染：endpoint=%s，error=%s", endpoint, exc)
        return None
    except Exception as exc:
        path = ""
        try:
            path = getattr(request, "path", "") or ""
        except Exception as exc:
            path = ""
            _log_warning("读取当前请求 path 失败，仍会记录链接构建异常：%s", exc)
        _log_warning("模板链接构建失败：endpoint=%s，path=%s，error=%s", endpoint, path, exc)
        return None


def get_manual_url(endpoint: Any = None, src: Any = None) -> Optional[str]:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint or resolve_manual_id(current_endpoint) is None:
        return None
    safe_src = normalize_manual_src_context(_resolve_manual_src(src))
    return safe_url_for("scheduler.config_manual_page", page=current_endpoint, src=safe_src)


def get_full_manual_section_url(endpoint: Any = None, src: Any = None) -> str:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint:
        return ""
    manual = build_manual_for_endpoint(current_endpoint, include_sections=False)
    if not manual:
        return ""
    safe_src = normalize_manual_src_context(_resolve_manual_src(src))
    base_url = safe_url_for("scheduler.config_manual_page", src=safe_src)
    if not base_url:
        return ""
    anchor = str(manual.get("full_manual_anchor") or "").strip()
    return base_url + anchor if anchor else base_url


def get_help_card(endpoint: Any = None, src: Any = None) -> Optional[Dict[str, Any]]:
    current_endpoint = _resolve_manual_endpoint(endpoint)
    if not current_endpoint:
        return None
    manual = build_manual_for_endpoint(current_endpoint, include_sections=False)
    if not manual:
        return None
    help_card = manual.get("help_card")
    if not help_card:
        return None
    return {
        "title": str(help_card.get("title") or "").strip(),
        "items": list(help_card.get("items") or []),
        "manual_url": get_manual_url(endpoint=current_endpoint, src=src),
    }
