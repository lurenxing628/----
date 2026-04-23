from __future__ import annotations

import html
import json
from typing import Any, Optional

from flask import current_app, jsonify, render_template, request

from core.infrastructure.errors import AppError, app_error_http_status


def wants_json_error_response() -> bool:
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best
    if best and "json" in best:
        return True
    if request.is_json:
        return True
    return False


def wants_json_error_response_or_default(
    *,
    default: bool = False,
    log_message: Optional[str] = None,
) -> bool:
    try:
        return wants_json_error_response()
    except Exception as exc:
        if log_message:
            logger = getattr(current_app, "logger", None)
            if logger is not None:
                logger.warning(log_message, exc)
        return bool(default)


def json_error_response(exc: AppError, *, payload: Optional[dict] = None):
    return jsonify(payload if payload is not None else exc.to_dict()), app_error_http_status(exc.code)


def _details_text(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False, indent=2)
    except Exception:
        return str(details)


def render_minimal_error_page(
    *,
    title: str,
    code: Any,
    message: str,
    details: Any = None,
    field_label: Optional[str] = None,
) -> str:
    title_text = html.escape(str(title or "发生错误"))
    code_text = html.escape(str(code or "未知"))
    message_text = html.escape(str(message or "发生未知错误，请查看日志。"))
    details_text = _details_text(details)
    extra_parts = []
    if field_label:
        extra_parts.append(f"<p><strong>相关字段：</strong>{html.escape(str(field_label))}</p>")
    if details_text:
        extra_parts.append(f"<pre>{html.escape(str(details_text))}</pre>")
    extra_html = "".join(extra_parts)
    return (
        "<!doctype html>"
        "<html lang=\"zh-CN\">"
        "<head>"
        "<meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        f"<title>{title_text}</title>"
        "<style>"
        "body{margin:0;font-family:'Segoe UI',sans-serif;background:#f5f1ea;color:#1f2933;}"
        ".shell{max-width:640px;margin:64px auto;padding:32px;background:#fff;border:1px solid #d9cbb8;"
        "border-radius:18px;box-shadow:0 20px 40px rgba(15,23,42,.08);}"
        "h1{margin:0 0 12px;font-size:28px;}.code,.message,.hint{margin:12px 0;line-height:1.6;}"
        "pre{margin:16px 0 0;padding:16px;border-radius:12px;background:#f8fafc;overflow:auto;white-space:pre-wrap;}"
        "</style>"
        "</head>"
        "<body>"
        "<main class=\"shell\">"
        f"<h1>{title_text}</h1>"
        f"<p class=\"code\"><strong>错误码：</strong>{code_text}</p>"
        f"<p class=\"message\"><strong>提示：</strong>{message_text}</p>"
        f"{extra_html}"
        "<p class=\"hint\">如果问题反复出现，请联系管理员查看运行日志。</p>"
        "</main>"
        "</body>"
        "</html>"
    )


def render_error_template(
    template_name: str = "error.html",
    *,
    title: str,
    code: Any,
    message: str,
    details: Any = None,
    field_label: Optional[str] = None,
) -> str:
    context = {
        "title": title,
        "code": code,
        "message": message,
        "details": details,
        "field_label": field_label,
    }
    try:
        return render_template(template_name, **context)
    except Exception as exc:
        logger = getattr(current_app, "logger", None)
        if logger is not None:
            logger.error("错误页渲染失败，已回退最小错误页：%s", exc)
        return render_minimal_error_page(
            title=title,
            code=code,
            message=message,
            details=details,
            field_label=field_label,
        )
