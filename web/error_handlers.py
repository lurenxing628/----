from __future__ import annotations

import traceback

from flask import request
from werkzeug.exceptions import RequestEntityTooLarge

from core.infrastructure.errors import AppError, ErrorCode, error_response
from web.ui_mode import render_ui_template as render_template


def _wants_json() -> bool:
    # 规则：API 路径优先；其次 Accept/JSON 头
    if request.path.startswith("/api/"):
        return True
    best = request.accept_mimetypes.best
    if best and "json" in best:
        return True
    if request.is_json:
        return True
    return False


def register_error_handlers(app):
    """注册 Flask 错误处理器（保证用户可见信息中文）。"""

    @app.errorhandler(AppError)
    def handle_app_error(e: AppError):
        app.logger.warning(f"业务错误：{e}")
        status_code = 413 if e.code == ErrorCode.FILE_TOO_LARGE else 400
        if _wants_json():
            return e.to_dict(), status_code
        return (
            render_template("error.html", title="发生错误", code=e.code.value, message=e.message, details=e.details),
            status_code,
        )

    @app.errorhandler(404)
    def handle_not_found(_e):
        payload = error_response(ErrorCode.NOT_FOUND, "请求的资源不存在")
        if _wants_json():
            return payload, 404
        return render_template("error.html", title="页面不存在", code=ErrorCode.NOT_FOUND.value, message="页面不存在或已被删除"), 404

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_too_large(_e):
        payload = error_response(ErrorCode.FILE_TOO_LARGE, "上传文件超过 16MB，请缩小文件后重试。")
        if _wants_json():
            return payload, 413
        return render_template(
            "error.html",
            title="文件过大",
            code=ErrorCode.FILE_TOO_LARGE.value,
            message="上传文件超过 16MB，请缩小文件后重试。",
        ), 413

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"服务器内部错误：{e}\n{traceback.format_exc()}")
        payload = error_response(ErrorCode.UNKNOWN_ERROR, "服务器内部错误，请查看日志")
        if _wants_json():
            return payload, 500
        return render_template("error.html", title="服务器内部错误", code=ErrorCode.UNKNOWN_ERROR.value, message="服务器内部错误，请查看日志"), 500

