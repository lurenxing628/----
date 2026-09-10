"""Workbench JSON boundaries do not infer a saved result from a redirect or HTML."""

from __future__ import annotations

import uuid
from functools import wraps
from typing import Literal, Union

from flask import current_app, g, jsonify, request, url_for
from werkzeug.exceptions import HTTPException

from core.errors import AppError, BusinessError, ValidationError, app_error_http_status
from core.models.workbench_command import WorkbenchCommandRejected, WorkbenchCommandUncertain


def failure(code, message, status, *, committed: Union[bool, Literal["unknown"]] = False, fields=None, request_key=None):
    reference = uuid.uuid4().hex
    error = {"code": code, "message": message, "fields": fields or [],
             "retryable": status >= 500, "request_ref": reference}
    if request_key is not None:
        error["request_key"] = request_key
        error["result_target"] = url_for("workbench.command_receipt", request_key=request_key)
    response = jsonify({"ok": False, "committed": committed, "error": error})
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def query_success(data, snapshot):
    return jsonify({"ok": True, "schema_version": 1, "data": data,
                    "meta": {"request_ref": uuid.uuid4().hex, "source": "production",
                             "time_basis": "factory_local", **snapshot}, "warnings": []})


def _domain_failure(exc):
    if isinstance(exc, ValidationError):
        fields = [{"path": exc.field, "message": exc.message}] if exc.field else []
        return failure("invalid_input", exc.message, 422, fields=fields)
    if isinstance(exc, BusinessError):
        missing = app_error_http_status(exc.code) == 404
        return failure("entity_not_found" if missing else "constraint_conflict", exc.message, 404 if missing else 409)
    current_app.logger.exception("工作台读取或领域存储失败 code=%s", exc.code.value)
    return failure("storage_failure", "本机数据读取失败，请查看运行日志后重试。", 500)


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
            return failure("invalid_input", "请求格式不正确，请检查输入后重试。", exc.code or 400)
        except Exception:
            current_app.logger.exception("工作台请求发生未预期错误 endpoint=%s", request.endpoint)
            is_write = request.method not in ("GET", "HEAD", "OPTIONS")
            return failure("storage_failure", "本机请求失败，请查看运行日志并核对结果后再操作。", 500,
                           committed="unknown" if is_write else False,
                           request_key=getattr(g, "workbench_request_key", None) if is_write else None)
    return wrapped
