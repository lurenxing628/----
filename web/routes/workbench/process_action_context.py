"""Retain exact process previews in memory; only confirmed commands write SQLite."""

from flask import g

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_process_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns
from core.models.workbench_resource_action import ResourceActionPreview, public_action_row

from .process_json import read_process_json
from .resource_action_context import resolve_context, retain_context
from .write_context import issue_write_context, validate_write_context

PREVIEW_SCOPE = "workbench-process-action-preview-v1"
EXPORT_SCOPE = "workbench-process-file-export-v1"


def action_preview(preview, command, *, kind=None, content=None, extra=None):
    ref, expiry = retain_context(PREVIEW_SCOPE, preview.document, content)
    body = preview.as_dict()
    context = issue_write_context(ref, [command], preview.intent())
    rejected = bool(body["summary"]["rejected"])
    if rejected:
        context["capabilities"][command] = False
        context["blocked_reasons"] = [{"action": command, "code": "constraint_conflict", "message": "请先处理预检中不能写入的行。"}]
    result = {"preview_ref": ref, "expires_at": expiry, "operation": body["operation"], "commit_policy": "atomic",
              "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
              "can_confirm": not rejected, "write_context": context,
              "columns": public_columns(kind or "route"), "scope": body["request"]["scope"]}
    if kind is not None:
        result.update(kind=kind, template_version=TEMPLATE_VERSION, instructions=INSTRUCTIONS)
        result.update({key: body["request"][key] for key in ("file_sha256", "format", "mode")})
    result.update(extra or {})
    return result


def confirmed_body(input_keys):
    body = read_process_json("工艺操作", 4 * 1024 * 1024)
    if set(body) != {"request_key", "write_token", "input"} or type(body["input"]) is not dict or set(body["input"]) != set(input_keys):
        raise WorkbenchCommandRejected("invalid_input", "工艺操作字段不完整或包含未知字段。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if type(body["write_token"]) is not str or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "请重新读取并核对资料后保存。", 400)
    return body


def checked_preview(ref, operation, command, write_token):
    if type(ref) is not str or not ref:
        raise WorkbenchCommandRejected("invalid_input", "操作预览不存在，请重新预检。", 400)
    document, content = resolve_context(PREVIEW_SCOPE, ref, "stale_write")
    preview = ResourceActionPreview(document)
    if preview.as_dict()["operation"] != operation:
        raise WorkbenchCommandRejected("stale_write", "预览不属于本次工艺操作。")
    validate_write_context(write_token, ref, command, preview.intent())
    return preview, content
