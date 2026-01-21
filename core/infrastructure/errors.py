from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any
import traceback

from flask import request, render_template


class ErrorCode(Enum):
    """错误码定义（与开发文档一致）。"""

    # 通用错误 (1xxx)
    SUCCESS = "0000"
    UNKNOWN_ERROR = "1000"
    VALIDATION_ERROR = "1001"
    NOT_FOUND = "1002"
    DUPLICATE_ENTRY = "1003"
    PERMISSION_DENIED = "1004"

    # 数据库错误 (2xxx)
    DB_CONNECTION_ERROR = "2001"
    DB_QUERY_ERROR = "2002"
    DB_TRANSACTION_ERROR = "2003"
    DB_INTEGRITY_ERROR = "2004"

    # 业务错误 - 人员模块 (3xxx)
    OPERATOR_NOT_FOUND = "3001"
    OPERATOR_ALREADY_EXISTS = "3002"
    OPERATOR_IN_USE = "3003"

    # 业务错误 - 设备模块 (4xxx)
    MACHINE_NOT_FOUND = "4001"
    MACHINE_ALREADY_EXISTS = "4002"
    MACHINE_IN_USE = "4003"
    MACHINE_NOT_AVAILABLE = "4004"

    # 业务错误 - 工艺模块 (5xxx)
    PART_NOT_FOUND = "5001"
    PART_ALREADY_EXISTS = "5002"
    ROUTE_PARSE_ERROR = "5003"
    OPERATION_DELETE_DENIED = "5004"
    EXTERNAL_GROUP_ERROR = "5005"

    # 业务错误 - 排产模块 (6xxx)
    BATCH_NOT_FOUND = "6001"
    BATCH_ALREADY_EXISTS = "6002"
    SCHEDULE_CONFLICT = "6003"
    SCHEDULE_LOCKED = "6004"
    RESOURCE_NOT_AVAILABLE = "6005"
    CALENDAR_ERROR = "6006"

    # 导入导出错误 (7xxx)
    EXCEL_READ_ERROR = "7001"
    EXCEL_WRITE_ERROR = "7002"
    EXCEL_FORMAT_ERROR = "7003"
    IMPORT_VALIDATION_ERROR = "7004"


@dataclass
class AppError(Exception):
    """应用异常基类（message 用于用户可见提示，必须中文）。"""

    code: ErrorCode
    message: str
    details: Optional[Dict[str, Any]] = None
    cause: Optional[Exception] = None

    def __str__(self):
        return f"[{self.code.value}] {self.message}"

    def to_dict(self) -> dict:
        result = {
            "success": False,
            "error": {
                "code": self.code.value,
                "message": self.message,
            },
        }
        if self.details:
            result["error"]["details"] = self.details
        return result


class ValidationError(AppError):
    def __init__(self, message: str, field: str = None, **kwargs):
        details = {"field": field} if field else None
        super().__init__(code=ErrorCode.VALIDATION_ERROR, message=message, details=details, **kwargs)


class NotFoundError(AppError):
    def __init__(self, resource_type: str, resource_id: str):
        super().__init__(
            code=ErrorCode.NOT_FOUND,
            message=f"{resource_type}“{resource_id}”不存在",
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class BusinessError(AppError):
    pass


def success_response(data=None, meta=None) -> dict:
    result = {"success": True}
    if data is not None:
        result["data"] = data
    if meta is not None:
        result["meta"] = meta
    return result


def error_response(code: ErrorCode, message: str, details=None) -> dict:
    error = {"code": code.value, "message": message}
    if details:
        error["details"] = details
    return {"success": False, "error": error}


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

