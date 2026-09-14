"""Bounded process payloads reject duplicate fields before domain validation."""

import json

from flask import request

from core.models.workbench_command import WorkbenchCommandRejected


def read_process_json(label, maximum):
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", label + "没有执行：提交的内容格式不正确，也不能在网址上附加条件。请刷新页面后重新提交。", 400)
    if request.content_length is not None and request.content_length > maximum:
        raise WorkbenchCommandRejected("capacity_exceeded", label + "没有执行：一次提交的内容太多，系统没有截断处理。请缩小范围后重新提交。", 413)
    raw = request.stream.read(maximum + 1)
    if len(raw) > maximum:
        raise WorkbenchCommandRejected("capacity_exceeded", label + "没有执行：一次提交的内容太多，系统没有截断处理。请缩小范围后重新提交。", 413)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WorkbenchCommandRejected("invalid_input", label + "没有执行：提交的内容有重复项。请刷新页面后重新提交。", 400)
            result[key] = value
        return result

    try:
        body = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        raise WorkbenchCommandRejected("invalid_input", label + "没有执行：提交的内容格式不正确。请刷新页面后重新提交。", 400) from exc
    if type(body) is not dict:
        raise WorkbenchCommandRejected("invalid_input", label + "没有执行：提交的内容不完整。请刷新页面后重新提交。", 400)
    return body
