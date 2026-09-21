"""工作台 JSON 信封：失败与查询成功两种响应形态，绝不从跳转或 HTML 推断"已保存"。

web 根辅助模块：只依赖 flask，不依赖 routes / bootstrap，两边都可以引用。
"""

from __future__ import annotations

import uuid
from typing import Literal, Union

from flask import jsonify, url_for


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


def query_success(data, snapshot, warnings=()):
    return jsonify({"ok": True, "schema_version": 1, "data": data,
                    "meta": {"request_ref": uuid.uuid4().hex, "source": "production",
                             "time_basis": "factory_local", **snapshot}, "warnings": list(warnings)})
