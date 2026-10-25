"""工作台 JSON 信封：失败与查询成功两种响应形态，绝不从跳转或 HTML 推断"已保存"。

web 根辅助模块：依赖 Flask 与中立 JSON/错误合同，供 routes / bootstrap 共同使用。
"""

from __future__ import annotations

import uuid
from typing import Literal, Union

from flask import Response, url_for

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json


def json_response(payload, *, byte_limit=None, too_large_code="query_too_large",
                  too_large_message="这次要读的数据超过上限，请缩小范围后重试。", status=200):
    """Encode the actual HTTP envelope once and send those same UTF-8 bytes."""
    content = canonical_json(payload).encode("utf-8")
    if byte_limit is not None and len(content) > byte_limit:
        raise WorkbenchCommandRejected(too_large_code, too_large_message, 413)
    return Response(content, status=status, content_type="application/json; charset=utf-8")


def failure_payload(code, message, status, *, committed: Union[bool, Literal["unknown"]] = False, fields=None,
                    request_key=None, conflicts=None, row_number=None, request_ref=None, result_target=None):
    reference = request_ref or uuid.uuid4().hex
    error = {"code": code, "message": message, "fields": fields or [],
             "retryable": status >= 500 and committed != "unknown", "request_ref": reference}
    if conflicts:
        error["conflicts"] = conflicts
    if row_number is not None:
        error["row_number"] = row_number
    if request_key is not None:
        error["request_key"] = request_key
        error["result_target"] = result_target or url_for("workbench.command_receipt", request_key=request_key)
    return {"ok": False, "committed": committed, "error": error}


def failure(code, message, status, *, committed: Union[bool, Literal["unknown"]] = False, fields=None,
            request_key=None, conflicts=None, row_number=None, request_ref=None, result_target=None):
    response = json_response(failure_payload(code, message, status, committed=committed, fields=fields,
        request_key=request_key, conflicts=conflicts, row_number=row_number, request_ref=request_ref,
        result_target=result_target), status=status)
    response.headers["Cache-Control"] = "no-store"
    return response


def query_payload(data, snapshot, warnings=()):
    return {"ok": True, "schema_version": 1, "data": data,
            "meta": {"request_ref": uuid.uuid4().hex, "source": "production",
                     "time_basis": "factory_local", **snapshot},
            "warnings": warnings if isinstance(warnings, list) else list(warnings)}


def query_success(data, snapshot, warnings=(), *, byte_limit=None, too_large_code="query_too_large",
                  too_large_message="这次要读的数据超过上限，请缩小范围后重试。"):
    return json_response(query_payload(data, snapshot, warnings), byte_limit=byte_limit,
                         too_large_code=too_large_code, too_large_message=too_large_message)
