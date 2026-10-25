"""Workbench JSON boundaries do not infer a saved result from a redirect or HTML.

信封本体在 web/api_responses.py；这里只负责把领域异常映射成失败信封。
"""

from __future__ import annotations

import uuid
from functools import wraps

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import AppError, BusinessError, ValidationError, app_error_http_status
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain
from core.services.workbench import messages
from web.api_responses import failure


def _outcome(exc, is_write):
    """A failed write may already have committed; its bound request key and result target lead to the receipt."""
    request_key = (exc.request_key if isinstance(exc, WorkbenchCommandUncertain)
                   else g.get("workbench_request_key") if is_write else None)
    return {"committed": "unknown" if is_write else False, "request_key": request_key,
            "result_target": g.get("workbench_result_target") if is_write else None}


def domain_failure(exc, *, is_write=False):
    if isinstance(exc, ValidationError):
        fields = [{"path": exc.field, "message": exc.message}] if exc.field else []
        return failure("invalid_input", exc.message, 422, fields=fields)
    if isinstance(exc, BusinessError):
        missing = app_error_http_status(exc.code) == 404
        return failure("entity_not_found" if missing else "constraint_conflict", exc.message, 404 if missing else 409)
    request_ref = uuid.uuid4().hex
    current_app.logger.exception("工作台读取或领域存储失败 code=%s request_ref=%s", exc.code.value, request_ref)
    return failure("storage_failure", messages.FAILURE, 500, request_ref=request_ref, **_outcome(exc, is_write))


def api_endpoint(function, *, readonly=False):
    @wraps(function)
    def wrapped(*args, **kwargs):
        is_write = not readonly and request.method not in ("GET", "HEAD", "OPTIONS")
        try:
            return function(*args, **kwargs)
        except WorkbenchCommandRejected as exc:
            # 500 拒绝的文案让用户“告知下方编号”：日志记下的编号就是响应里的这一个。
            request_ref = uuid.uuid4().hex
            if exc.status >= 500:
                current_app.logger.exception("工作台请求失败 code=%s request_ref=%s", exc.code, request_ref)
            return failure(exc.code, str(exc), exc.status, conflicts=exc.conflicts, row_number=exc.row_number,
                           request_ref=request_ref)
        except WorkbenchCommandUncertain as exc:
            request_ref = uuid.uuid4().hex
            current_app.logger.exception("工作台写入结果待核实 request_key=%s request_ref=%s", exc.request_key, request_ref)
            return failure("storage_failure", str(exc), 500, request_ref=request_ref, **_outcome(exc, is_write))
        except AppError as exc:
            return domain_failure(exc, is_write=is_write)
        except HTTPException as exc:
            return failure("invalid_input", "提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。", exc.code or 400)
        except Exception as exc:
            request_ref = uuid.uuid4().hex
            current_app.logger.exception("工作台请求发生未预期错误 endpoint=%s request_ref=%s", request.endpoint, request_ref)
            return failure("storage_failure", messages.FAILURE, 500, request_ref=request_ref, **_outcome(exc, is_write))
    return wrapped


def read_endpoint(function):
    return api_endpoint(function, readonly=True)
