"""Retain exact process previews in memory; only confirmed commands write SQLite."""

from core.models.workbench_process_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns
from core.models.workbench_resource_action import public_action_row
from core.shared.key_sets import keys_conform

from .process_json import process_command_body
from .request_json import rejecter
from .resource_action_context import EXPIRED_MESSAGE
from .write_context import preview_write_context, resolve_action_preview, retain_action_preview

# 工艺文件导入和零件批量删除出了预检结果后，弹窗里的预检按钮都改叫「重新预检」；这里的提示都在那之后出现。
PREVIEW_SCOPE = "workbench-process-action-preview-v1"
EXPORT_SCOPE = "workbench-process-file-export-v1"


def action_preview(preview, command, *, kind=None, extra):
    ref, expiry = retain_action_preview(PREVIEW_SCOPE, preview)
    body = preview.as_dict()
    context = preview_write_context(ref, expiry, [command])
    rejected = bool(body["summary"]["rejected"])
    if rejected:
        context["capabilities"][command] = False
        context["blocked_reasons"] = [{"action": command, "code": "constraint_conflict", "message": "预检里有不能保存的行，工艺资料没有改动。请修好标红的行后点「重新预检」。"}]
    result = {"preview_ref": ref, "expires_at": expiry, "operation": body["operation"], "commit_policy": "atomic",
              "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
              "can_confirm": not rejected, "write_context": context,
              "columns": public_columns(kind or "route"), "scope": body["request"]["scope"]}
    if kind is not None:
        result.update(kind=kind, template_version=TEMPLATE_VERSION, instructions=INSTRUCTIONS[kind])
        result.update({key: body["request"][key] for key in ("format", "mode")})
    result.update(extra)
    return result


PROCESS_INCOMPLETE = "提交的内容不完整或有多余项，工艺资料还没有保存。请刷新页面后重新填写。"
PROCESS_STALE = "本页数据已过期，工艺资料还没有保存。请点「刷新资料」后重新核对再保存。"


def confirmed_body(input_keys):
    """Confirm a process preview: the command envelope whose input holds exactly the entry's ``input_keys``."""
    body = process_command_body("工艺操作", 4 * 1024 * 1024, incomplete=PROCESS_INCOMPLETE, stale=PROCESS_STALE)
    if not keys_conform(body["input"], input_keys):
        rejecter(PROCESS_INCOMPLETE)()
    return body


def checked_preview(ref, operation, write_token):
    return resolve_action_preview(PREVIEW_SCOPE, ref, operation, write_token, expired_message=EXPIRED_MESSAGE,
                                  mismatch_message="预检结果和这次工艺操作对不上，工艺资料没有改动。请点「重新预检」。")
