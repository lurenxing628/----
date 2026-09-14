"""Server-owned immutable action/export contexts; public tokens hold short keys."""

import json
import time
from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from threading import RLock

from flask import current_app
from werkzeug.exceptions import HTTPException

from core.errors import AppError, ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_resource_action import public_action_row, resource_scope
from core.models.workbench_resource_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns
from core.models.workbench_resource_query import ResourcePageRequest
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import api_endpoint
from .material_actions_context import json_body, opaque_ref
from .write_context import issue_write_context, validate_write_context

PREVIEW_SCOPE = "workbench-resource-preview-v1"
EXPORT_SCOPE = "workbench-resource-export-v1"
EXTENSION = "workbench_resource_action_contexts_v1"
LOCK = RLock()


@dataclass(frozen=True)
class RetainedContext:
    document: str
    content: object
    expires_at: float


def read_endpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (AppError, HTTPException, WorkbenchCommandRejected):
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", "资源预检或下载没有完成，数据没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500) from exc
    return api_endpoint(wrapped)


def scope_input(kind, body):
    scope = resource_scope(kind, body["scope"])
    query = ResourcePageRequest(kind=kind, **scope, size=body.get("page_size", 20))
    return scope, query.scope(), opaque_ref(body["snapshot_ref"], "snapshot_ref")


def _store():
    store = current_app.extensions.setdefault(EXTENSION, {})
    now = time.time()
    for key in list(store):
        if store[key].expires_at <= now:
            del store[key]
    return store


def retain_context(namespace, document, content=None):
    key = input_fingerprint({"namespace": namespace, "document": document})
    binding = canonical_json({"version": 1, "source": "production", "context_key": key})
    token, expiry = issue_public_token_with_expiry(namespace, binding, ttl_seconds=900)
    with LOCK:
        store = _store()
        previous = store.get(key)
        if previous:
            if previous.document != document or previous.content != content:
                raise RuntimeError("操作引用对应不同原始内容，未覆盖预览。")
            expiry = max(expiry, previous.expires_at)
        store[key] = RetainedContext(document, content, expiry)
    return token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")


def resolve_context(namespace, ref, code):
    try:
        binding = json.loads(resolve_public_token(namespace, ref, message="预检结果已过期，数据没有改动。请重新点「开始预检」。", field="preview_ref"))
    except (ValidationError, ValueError) as exc:
        raise WorkbenchCommandRejected(code, "预检结果已过期，数据没有改动，范围也没有自动更换。请重新点「开始预检」。") from exc
    if binding.get("version") != 1 or binding.get("source") != "production":
        raise WorkbenchCommandRejected(code, "预检结果和这次操作对不上，数据没有改动。请重新点「开始预检」。")
    with LOCK:
        value = _store().get(binding["context_key"])
        if value is None:
            raise WorkbenchCommandRejected(code, "预检结果已过期，数据没有改动；系统没有拿页面上的内容凑一份。请重新点「开始预检」。")
        return value.document, value.content


def issue_preview(kind, preview, content=None):
    ref, expires_at = retain_context(PREVIEW_SCOPE, preview.document, content)
    body = preview.as_dict()
    action = body["operation"]
    context = issue_write_context(ref, [action], preview.intent())
    rejected = body["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict", "message": "这一批里有不能提交的行，数据没有改动。请修好标红的行后重新点「开始预检」。"}]
    result = {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
              "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
              "can_confirm": not rejected, "write_context": context, "columns": public_columns(kind), "scope": body["request"]["scope"]}
    if action.endswith(".import"):
        result.update({key: body["request"][key] for key in ("file_sha256", "format", "mode")})
        result.update(template_version=TEMPLATE_VERSION, instructions=INSTRUCTIONS)
        if kind == "op_type":
            result["category"] = body["request"]["scope"]["category"]
    return result


def resolve_preview(ref, action, write_token):
    from core.models.workbench_resource_action import ResourceActionPreview

    document, content = resolve_context(PREVIEW_SCOPE, ref, "stale_write")
    preview = ResourceActionPreview(document)
    if preview.as_dict()["operation"] != action:
        raise WorkbenchCommandRejected("stale_write", "预检结果和这次操作或这条记录对不上，数据没有改动。请重新点「开始预检」。")
    validate_write_context(write_token, ref, action, preview.intent())
    return preview, content
