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
        context["blocked_reasons"] = [{"action": command, "code": "constraint_conflict", "message": "预检里有不能保存的行，工艺资料没有改动。请修好标红的行后重新点「开始预检」。"}]
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
        raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，工艺资料还没有保存。请刷新页面后重新填写。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if type(body["write_token"]) is not str or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "本页数据已过期，工艺资料还没有保存。请点「刷新资料」后重新核对再保存。", 400)
    return body


def checked_preview(ref, operation, command, write_token):
    if type(ref) is not str or not ref:
        raise WorkbenchCommandRejected("invalid_input", "预检结果已过期，工艺资料没有改动。请重新点「开始预检」。", 400)
    document, content = resolve_context(PREVIEW_SCOPE, ref, "stale_write")
    preview = ResourceActionPreview(document)
    if preview.as_dict()["operation"] != operation:
        raise WorkbenchCommandRejected("stale_write", "预检结果和这次工艺操作对不上，工艺资料没有改动。请重新点「开始预检」。")
    validate_write_context(write_token, ref, command, preview.intent())
    return preview, content
