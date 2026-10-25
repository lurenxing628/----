from __future__ import annotations

import traceback

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge

from core.errors import AppError, ErrorCode, app_error_http_status, error_response
from web.error_boundary import (
    build_user_visible_app_error_payload,
    render_error_template,
    wants_json_error_response,
)


def _request_log_context() -> str:
    """AppError 日志的请求上下文（method/path/endpoint），用于区分同文案业务错误来自哪个接口。"""
    return "method={} path={} endpoint={}".format(request.method, request.path, request.endpoint or "-")


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
        payload = build_user_visible_app_error_payload(e)
        if wants_json_error_response():
            return payload, status_code
        error = payload["error"]
        details = error.get("details")
        field_label = details["field"] if details else None
        return (
            render_error_template(
                title="发生错误",
                message=error["message"],
                field_label=field_label,
            ),
            status_code,
        )

    @app.errorhandler(404)
    def handle_not_found(_e):
        payload = error_response(ErrorCode.NOT_FOUND, "页面不存在或已被删除。")
        if wants_json_error_response():
            return payload, 404
        return (
            render_error_template(
                title="页面不存在",
                message="页面不存在或已被删除。",
                field_label=None,
            ),
            404,
        )

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_e):
        payload = error_response(ErrorCode.FILE_TOO_LARGE, "文件超过 16 MB，请缩小文件后重试。")
        if wants_json_error_response():
            return payload, 413
        return (
            render_error_template(
                title="文件过大",
                message="文件超过 16 MB，请缩小文件后重试。",
                field_label=None,
            ),
            413,
        )

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"服务器内部错误：{e}\n{traceback.format_exc()}")
        payload = error_response(ErrorCode.UNKNOWN_ERROR, "系统出错，这次操作没有完成。请刷新重试；仍不行请联系维护人员。")
        if wants_json_error_response():
            return payload, 500
        return (
            render_error_template(
                title="系统出错",
                message="系统出错，这次操作没有完成。请刷新重试；仍不行请联系维护人员。",
                field_label=None,
            ),
            500,
        )
