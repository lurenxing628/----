from __future__ import annotations

import traceback
from typing import Any, Optional

from werkzeug.exceptions import RequestEntityTooLarge

from core.infrastructure.errors import AppError, ErrorCode, app_error_http_status, error_response
from core.services.scheduler import ConfigService
from web.error_boundary import render_error_template, wants_json_error_response_or_default


def _resolve_field_label(details: Any) -> Optional[str]:
    if not isinstance(details, dict):
        return None
    field = str(details.get("field") or "").strip()
    return ConfigService.get_field_label(field) if field else None


def register_error_handlers(app):
    """注册 Flask 错误处理器，保证用户可见信息中文。"""

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        app.logger.warning(f"业务错误：{e}")
        status_code = app_error_http_status(e.code)
        if wants_json_error_response_or_default(log_message="业务错误响应分类失败，已回退 HTML 400：%s"):
            return e.to_dict(), status_code
        return (
            render_error_template(
                title="发生错误",
                code=e.code.value,
                message=e.message,
                details=e.details,
                field_label=_resolve_field_label(e.details),
            ),
            status_code,
        )

    @app.errorhandler(404)
    def handle_not_found(_e):
        payload = error_response(ErrorCode.NOT_FOUND, "请求的资源不存在")
        if wants_json_error_response_or_default(log_message="404 响应分类失败，已回退 HTML 404：%s"):
            return payload, 404
        return (
            render_error_template(
                title="页面不存在",
                code=ErrorCode.NOT_FOUND.value,
                message="页面不存在或已被删除",
                field_label=None,
            ),
            404,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_e):
        payload = error_response(ErrorCode.FILE_TOO_LARGE, "上传文件超过 16MB，请缩小文件后重试。")
        if wants_json_error_response_or_default(log_message="413 响应分类失败，已回退 HTML 413：%s"):
            return payload, 413
        return (
            render_error_template(
                title="文件过大",
                code=ErrorCode.FILE_TOO_LARGE.value,
                message="上传文件超过 16MB，请缩小文件后重试。",
                field_label=None,
            ),
            413,
        )

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"服务器内部错误：{e}\n{traceback.format_exc()}")
        payload = error_response(ErrorCode.UNKNOWN_ERROR, "服务器内部错误，请查看日志")
        if wants_json_error_response_or_default(log_message="500 响应分类失败，已回退 HTML 500：%s"):
            return payload, 500
        return (
            render_error_template(
                title="服务器内部错误",
                code=ErrorCode.UNKNOWN_ERROR.value,
                message="服务器内部错误，请查看日志",
                field_label=None,
            ),
            500,
        )
