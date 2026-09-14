"""Batch request shapes and signed previews, using common contexts and receipts."""

import json
import re
from typing import Dict, Union

from flask import g, request

from core.errors import ValidationError
from core.models.workbench_batch import object_fields
from core.models.workbench_batch_query import batch_scope
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, validate_request_key
from web.public_token_registry import issue_public_token, resolve_public_token

PREVIEW_SCOPE = "workbench-batch-preview-v1"


def read_scope():
    values: Dict[str, Union[str, int]] = dict(request.args)
    if any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "筛选条件有重复项，列表没有变化。请刷新页面后重新选择。", 400)
    for key in ("page", "size"):
        if key in values:
            raw = request.args[key]
            if re.fullmatch(r"[1-9][0-9]{0,6}", raw) is None:
                raise WorkbenchCommandRejected("invalid_input", "页码或每页条数填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
            values[key] = int(raw)
    return batch_scope(values)


def json_body():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，还没有保存。请刷新页面后重新填写。", 400)
    return request.get_json()


def command_body():
    body = object_fields(json_body(), ("request_key", "write_token", "input"), ("request_key", "write_token", "input"))
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if not isinstance(body["write_token"], str) or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "本页数据已过期，还没有保存。请点「刷新资料」后重新填写。", 400)
    return body


def save_preview(action, ref, payload, fingerprint):
    return issue_public_token(PREVIEW_SCOPE, canonical_json({"action": action, "ref": ref, "input": payload, "fingerprint": fingerprint}), ttl_seconds=900)


def load_preview(token, action, ref):
    try:
        binding = json.loads(resolve_public_token(PREVIEW_SCOPE, token, message="预检结果已过期，还没有保存。请重新点「预览变更」。", field="preview_ref"))
    except (ValidationError, ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("stale_write", "预检结果已过期，系统没有自动重做，也没有保存。请重新点「预览变更」。") from exc
    if not isinstance(binding, dict) or binding.get("action") != action or binding.get("ref") != ref:
        raise WorkbenchCommandRejected("stale_write", "预检结果和当前批次操作对不上，还没有保存。请重新点「预览变更」。")
    return binding
