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
        raise WorkbenchCommandRejected("invalid_input", "筛选参数不能重复。", 400)
    for key in ("page", "size"):
        if key in values:
            raw = request.args[key]
            if re.fullmatch(r"[1-9][0-9]{0,6}", raw) is None:
                raise WorkbenchCommandRejected("invalid_input", "页码或每页条数不正确。", 400)
            values[key] = int(raw)
    return batch_scope(values)


def json_body():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "请求必须使用JSON且不带查询参数。", 400)
    return request.get_json()


def command_body():
    body = object_fields(json_body(), ("request_key", "write_token", "input"), ("request_key", "write_token", "input"))
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if not isinstance(body["write_token"], str) or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "缺少保存上下文，请重新读取。", 400)
    return body


def save_preview(action, ref, payload, fingerprint):
    return issue_public_token(PREVIEW_SCOPE, canonical_json({"action": action, "ref": ref, "input": payload, "fingerprint": fingerprint}), ttl_seconds=900)


def load_preview(token, action, ref):
    try:
        binding = json.loads(resolve_public_token(PREVIEW_SCOPE, token, message="预览已失效，请重新预览。", field="preview_ref"))
    except (ValidationError, ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("stale_write", "预览已失效，请重新预览；未自动重做。") from exc
    if not isinstance(binding, dict) or binding.get("action") != action or binding.get("ref") != ref:
        raise WorkbenchCommandRejected("stale_write", "预览与当前批次操作不一致。")
    return binding
