from __future__ import annotations

import traceback
from typing import Any, List, Optional, Tuple

from flask import has_request_context, request
from werkzeug.exceptions import RequestEntityTooLarge

from core.errors import AppError, ErrorCode, app_error_http_status, error_response
from web.error_boundary import (
    build_user_visible_app_error_payload,
    get_user_visible_field_label,
    render_error_template,
    user_visible_app_error_details,
    user_visible_app_error_message,
    wants_json_error_response_or_default,
)


def _resolve_field_label(details: Any) -> Optional[str]:
    if not isinstance(details, dict):
        return None
    field = str(details.get("field") or "").strip()
    if not field:
        return None
    return get_user_visible_field_label(field) or field


def _request_log_context() -> str:
    """
    AppError 日志的请求上下文（method/path/endpoint），用于区分同文案业务错误来自哪个接口。

    handler 理论上可能在无请求上下文时被手动调用（如测试/后台脚本），
    此时降级为占位符，不影响日志写入本身。
    """
    if not has_request_context():
        return "method=- path=- endpoint=-"
    return "method={} path={} endpoint={}".format(request.method, request.path, request.endpoint or "-")


def _html_error_details(details: Any) -> Tuple[Any, Optional[str]]:
    if not isinstance(details, dict):
        return details, None
    labels: List[str] = []
    field_label = _resolve_field_label(details)
    if field_label:
        labels.append(field_label)
    for item in details.get("invalid_query_labels") or []:
        text = str(item or "").strip()
        if text and text not in labels:
            labels.append(text)
    if labels:
        return None, "、".join(labels)
    return details, field_label


def register_error_handlers(app):
    """注册 Flask 错误处理器，保证用户可见信息中文。"""

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        request_context = _request_log_context()
        if e.internal_details:
            app.logger.warning("业务错误：%s %s internal_details=%s", e, request_context, e.internal_details)
        else:
            app.logger.warning("业务错误：%s %s", e, request_context)
        status_code = app_error_http_status(e.code)
        user_message = user_visible_app_error_message(e)
        user_details = user_visible_app_error_details(e)
        if wants_json_error_response_or_default(log_message="业务错误响应分类失败，已回退 HTML 400：%s"):
            return build_user_visible_app_error_payload(e), status_code
        html_details, field_label = _html_error_details(user_details)
        return (
            render_error_template(
                title="发生错误",
                code=None,
                message=user_message,
                details=html_details,
                field_label=field_label,
            ),
            status_code,
        )

    @app.errorhandler(404)
    def handle_not_found(_e):
        payload = error_response(ErrorCode.NOT_FOUND, "页面不存在或已被删除。")
        if wants_json_error_response_or_default(log_message="404 响应分类失败，已回退 HTML 404：%s"):
            return payload, 404
        return (
            render_error_template(
                title="页面不存在",
                code=None,
                message="页面不存在或已被删除。",
                field_label=None,
            ),
            404,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_e):
        payload = error_response(ErrorCode.FILE_TOO_LARGE, "文件超过 16 MB，请缩小文件后重试。")
        if wants_json_error_response_or_default(log_message="413 响应分类失败，已回退 HTML 413：%s"):
            return payload, 413
        return (
            render_error_template(
                title="文件过大",
                code=None,
                message="文件超过 16 MB，请缩小文件后重试。",
                field_label=None,
            ),
            413,
        )

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"服务器内部错误：{e}\n{traceback.format_exc()}")
        payload = error_response(ErrorCode.UNKNOWN_ERROR, "系统出错，这次操作没有完成。请刷新重试；仍不行请联系维护人员。")
        if wants_json_error_response_or_default(log_message="500 响应分类失败，已回退 HTML 500：%s"):
            return payload, 500
        return (
            render_error_template(
                title="系统出错",
                code=None,
                message="系统出错，这次操作没有完成。请刷新重试；仍不行请联系维护人员。",
                field_label=None,
            ),
            500,
        )
