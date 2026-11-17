"""Server-owned action/export values held directly by public token bindings."""

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from core.errors import ValidationError
from core.models.workbench_action_values import UPSERT_IMPORT_MODES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import public_action_row, resource_scope_request, wire_resource_scope
from core.models.workbench_resource_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.shared.key_sets import keys_conform
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import worded_read_endpoint
from .request_json import (
    BodyTexts,
    opaque_ref,
    read_json_body,
    read_upload_file,
    read_upload_form,
    rejecter,
    single_value_arguments,
)
from .write_context import preview_write_context, retain_action_preview

PREVIEW_SCOPE = "workbench-resource-preview-v1"
EXPORT_SCOPE = "workbench-resource-export-v1"
EXPIRED_MESSAGE = "预检结果已过期，数据没有改动，范围也没有自动更换。请重新预检。"
IMPORT_MISMATCH_MESSAGE = "预检结果和这次操作对不上，数据没有改动。请点「重新预检」。"
STALE_REF_MESSAGE = "这次操作的编号已失效，数据没有改动。请关掉弹窗后重新打开。"
CONFIRM_MISMATCH_MESSAGE = "只能确认刚才预检过的那一批，数据没有改动。请点「重新预检」。"
PAGE_STALE_MESSAGE = "本页数据已过期，数据没有改动。请刷新页面后重新填写。"
# Duplicate keys share the syntax-error text rather than silently taking the last scope or ref.
BODY = BodyTexts(transport="提交的内容格式不正确，数据没有改动。请刷新页面后重新填写。",
                 malformed="提交的内容格式不正确或有重复项，数据没有改动。请刷新页面后重新填写。",
                 incomplete="提交的内容不完整或有多余项，数据没有改动。请刷新页面后重新填写。")


@dataclass(frozen=True)
class RetainedContext:
    document: object
    content: object


read_endpoint = worded_read_endpoint("资源预检或下载没有完成，数据没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。")


def json_body(required, optional=()):
    body = read_json_body(BODY)
    if not keys_conform(body, required, optional):
        rejecter(BODY.incomplete)()
    return body


def scope_input(kind, body):
    """The viewed list's validated request, its read-binding scope and snapshot token."""
    request = resource_scope_request(kind, body["scope"], size=body.get("page_size", 20))
    return request, request.scope(), opaque_ref(body["snapshot_ref"], STALE_REF_MESSAGE)


def export_identity(arguments):
    """The JSON view of export arguments: the request's wire scope plus any explicit refs."""
    return {**{key: value for key, value in arguments.items() if key != "request"},
            "scope": wire_resource_scope(arguments["request"])}


def retain_context(namespace, document, content, *, key):
    """Retain an export or field-report document, read-only, with its read binding or parsed source."""
    token, expiry = issue_public_token_with_expiry(namespace, RetainedContext(MappingProxyType(document), content),
                                                  key=key, ttl_seconds=900)
    return token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")


def resolve_context(namespace, ref, code, *, expired_message=EXPIRED_MESSAGE):
    try:
        value = resolve_public_token(namespace, ref, message="预检结果已过期，数据没有改动。请重新预检。", field="preview_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected(code, expired_message) from exc
    return value.document, value.content


def issue_preview(kind, preview):
    ref, expires_at = retain_action_preview(PREVIEW_SCOPE, preview)
    body = preview.as_dict()
    action = body["operation"]
    context = preview_write_context(ref, expires_at, [action])
    rejected = body["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict", "message": "这一批里有不能提交的行，数据没有改动。请修好标红的行后重新预检。"}]
    result = {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
              "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
              "can_confirm": not rejected, "write_context": context, "columns": public_columns(kind)}
    if action.endswith(".import"):
        result.update({key: body["request"][key] for key in ("actual_source_ref", "format", "mode")})
        result.update(template_version=TEMPLATE_VERSION, instructions=INSTRUCTIONS[kind])
        if kind == "op_type":
            result["category"] = body["request"]["category"]
    else:
        result["scope"] = body["request"]["scope"]
    return result


def issue_file_preview(preview, *, columns, instructions, template_version):
    """导入预检的公开响应。关联资料与日历文件家族共用；资源家族的 issue_preview 还要兼顾批量删除，不并进来。"""
    ref, expires_at = retain_action_preview(PREVIEW_SCOPE, preview)
    body = preview.as_dict()
    action = body["operation"]
    context = preview_write_context(ref, expires_at, [action])
    rejected = body["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict",
                                       "message": "这一批里有不能提交的行，数据没有改动。请修好标红的行后重新预检。"}]
    return {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
            "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
            "can_confirm": not rejected, "write_context": context, "columns": columns,
            "scope": body["request"]["scope"], "actual_source_ref": body["request"]["actual_source_ref"],
            "format": body["request"]["format"], "mode": body["request"]["mode"],
            "template_version": template_version, "instructions": instructions}


def upload_body():
    """导入预检的 multipart 请求：恰好一个文件，外加格式与导入方式，多一项少一项都拒绝。"""
    shape = "请上传一个文件并选好格式和导入方式；数据没有改动。选好后点「开始预检」。"
    form = read_upload_form({"format", "mode"}, transport=shape, shape=shape)
    fmt, mode = form["format"], form["mode"]
    if fmt not in FILE_FORMATS or mode not in UPSERT_IMPORT_MODES:
        raise WorkbenchCommandRejected("invalid_input", "只支持 CSV 或 XLSX 按编号增量导入；数据没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = read_upload_file("文件超过本机允许的大小，一行都没有导入。请缩小文件后重新选择，再点「开始预检」。")
    return content, fmt, mode


def admit_export_selection(body, *, explicit_value="selected", message):
    selection = body["selection"]
    if selection not in ("all", "filtered", explicit_value) or ("refs" in body) != (selection == explicit_value):
        raise WorkbenchCommandRejected("invalid_input", message, 400)
    return selection


def download_query(required):
    """A download's query string: exactly the required keys, each given once."""
    return single_value_arguments(required, required=required,
                                  message="下载条件不完整或有多余项，没有开始下载。请刷新页面后重新点「导出」。")


def download_args(required):
    fmt = download_query(required)["format"]
    if fmt not in FILE_FORMATS:
        raise WorkbenchCommandRejected("invalid_input", "下载只支持 CSV 或 XLSX 格式，没有开始下载。请重新选择格式后点「导出」。", 400)
    return fmt


def file_response(download):
    from io import BytesIO

    from flask import send_file

    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    return response
