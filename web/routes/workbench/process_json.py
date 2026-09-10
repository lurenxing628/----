"""Bounded process payloads reject duplicate fields before domain validation."""

import json

from flask import request

from core.models.workbench_command import WorkbenchCommandRejected


def read_process_json(label, maximum):
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", label + "必须使用JSON正文，不能带其他URL参数。", 400)
    if request.content_length is not None and request.content_length > maximum:
        raise WorkbenchCommandRejected("capacity_exceeded", label + "正文过大，未截断输入。", 413)
    raw = request.stream.read(maximum + 1)
    if len(raw) > maximum:
        raise WorkbenchCommandRejected("capacity_exceeded", label + "正文过大，未截断输入。", 413)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise WorkbenchCommandRejected("invalid_input", label + "JSON包含重复字段。", 400)
            result[key] = value
        return result

    try:
        body = json.loads(raw, object_pairs_hook=unique)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        raise WorkbenchCommandRejected("invalid_input", label + "正文不是有效JSON。", 400) from exc
    if type(body) is not dict:
        raise WorkbenchCommandRejected("invalid_input", label + "正文必须是对象。", 400)
    return body
