from __future__ import annotations

import traceback

from flask import request

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
        if _wants_json():
            return e.to_dict(), 400
        return render_template("error.html", title="发生错误", code=e.code.value, message=e.message, details=e.details), 400

    @app.errorhandler(404)
    def handle_not_found(_e):
        payload = error_response(ErrorCode.NOT_FOUND, "请求的资源不存在")
        if _wants_json():
            return payload, 404
        return render_template("error.html", title="页面不存在", code=ErrorCode.NOT_FOUND.value, message="页面不存在或已被删除"), 404

    @app.errorhandler(500)
    def handle_internal_error(e):
        app.logger.error(f"服务器内部错误：{e}\n{traceback.format_exc()}")
        payload = error_response(ErrorCode.UNKNOWN_ERROR, "服务器内部错误，请查看日志")
        if _wants_json():
            return payload, 500
        return render_template("error.html", title="服务器内部错误", code=ErrorCode.UNKNOWN_ERROR.value, message="服务器内部错误，请查看日志"), 500

