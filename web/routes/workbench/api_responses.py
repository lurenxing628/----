"""Workbench JSON boundaries do not infer a saved result from a redirect or HTML.

信封本体在 web/api_responses.py；这里只负责把领域异常映射成失败信封。
"""

from __future__ import annotations

from functools import wraps

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import AppError, BusinessError, ValidationError, app_error_http_status
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench import messages
from web.api_responses import failure


def _domain_failure(exc):
    if isinstance(exc, ValidationError):
        fields = [{"path": exc.field, "message": exc.message}] if exc.field else []
        return failure("invalid_input", exc.message, 422, fields=fields)
    if isinstance(exc, BusinessError):
        missing = app_error_http_status(exc.code) == 404
        return failure("entity_not_found" if missing else "constraint_conflict", exc.message, 404 if missing else 409)
    current_app.logger.exception("工作台读取或领域存储失败 code=%s", exc.code.value)
    return failure("storage_failure", messages.FAILURE, 500)


def api_endpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except WorkbenchCommandRejected as exc:
            if exc.status >= 500:
                current_app.logger.exception("工作台请求失败 code=%s", exc.code)
            return failure(exc.code, str(exc), exc.status)
        except WorkbenchCommandUncertain as exc:
            current_app.logger.exception("工作台写入结果待核实 request_key=%s", exc.request_key)
            return failure("storage_failure", str(exc), 500, committed="unknown", request_key=exc.request_key)
        except AppError as exc:
            return _domain_failure(exc)
        except HTTPException as exc:
            return failure("invalid_input", "提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。", exc.code or 400)
        except Exception:
            current_app.logger.exception("工作台请求发生未预期错误 endpoint=%s", request.endpoint)
            is_write = request.method not in ("GET", "HEAD", "OPTIONS")
            return failure("storage_failure", messages.FAILURE, 500,
                           committed="unknown" if is_write else False,
                           request_key=getattr(g, "workbench_request_key", None) if is_write else None)
    return wrapped
