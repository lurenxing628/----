"""Server-owned action/export values held directly by public token bindings."""

from dataclasses import dataclass
from datetime import datetime
from functools import wraps
from types import MappingProxyType

from werkzeug.exceptions import HTTPException

from core.errors import AppError, ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import public_action_row, resource_page_scope
from core.models.workbench_resource_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns
from web.public_token_registry import issue_public_token_with_expiry, resolve_public_token

from .api_responses import api_endpoint
from .material_actions_context import json_body, opaque_ref
from .request_json import read_upload_file
from .write_context import preview_write_context, validate_preview_confirmation

PREVIEW_SCOPE = "workbench-resource-preview-v1"
EXPORT_SCOPE = "workbench-resource-export-v1"


@dataclass(frozen=True)
class RetainedContext:
    document: object
    content: object


def read_endpoint(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except (AppError, HTTPException, WorkbenchCommandRejected):
            raise
        except Exception as exc:
            raise WorkbenchCommandRejected("storage_failure", "资源预检或下载没有完成，数据没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500) from exc
    return api_endpoint(wrapped, readonly=True)


def scope_input(kind, body):
    _, query = resource_page_scope(kind, body["scope"], size=body.get("page_size", 20))
    return query, query.scope(), opaque_ref(body["snapshot_ref"])


def retain_context(namespace, document, content=None, *, key=None):
    from .read_context import fact_value

    identity = fact_value(document) if key is None else key
    retained = MappingProxyType(document) if isinstance(document, dict) else document
    token, expiry = issue_public_token_with_expiry(namespace, RetainedContext(retained, content),
                                                  key=identity, ttl_seconds=900)
    return token, datetime.fromtimestamp(expiry).isoformat(timespec="seconds")


def resolve_context(namespace, ref, code):
    try:
        value = resolve_public_token(namespace, ref, message="预检结果已过期，数据没有改动。请重新预检。", field="preview_ref")
    except ValidationError as exc:
        raise WorkbenchCommandRejected(code, "预检结果已过期，数据没有改动，范围也没有自动更换。请重新预检。") from exc
    return value.document, value.content


def issue_preview(kind, preview, content=None):
    ref, expires_at = retain_context(PREVIEW_SCOPE, preview.document, content)
    body = preview.as_dict()
    action = body["operation"]
    context = preview_write_context(ref, expires_at, [action])
    rejected = body["summary"]["rejected"] != 0
    if rejected:
        context["capabilities"][action] = False
        context["blocked_reasons"] = [{"action": action, "code": "constraint_conflict", "message": "这一批里有不能提交的行，数据没有改动。请修好标红的行后重新预检。"}]
    result = {"preview_ref": ref, "expires_at": expires_at, "operation": action, "commit_policy": "atomic",
              "summary": body["summary"], "rows": [public_action_row(row) for row in body["rows"]],
              "can_confirm": not rejected, "write_context": context, "columns": public_columns(kind), "scope": body["request"]["scope"]}
    if action.endswith(".import"):
        result.update({key: body["request"][key] for key in ("actual_source_ref", "format", "mode")})
        result.update(template_version=TEMPLATE_VERSION, instructions=INSTRUCTIONS[kind])
        if kind == "op_type":
            result["category"] = body["request"]["scope"]["category"]
    return result


def issue_file_preview(preview, content, *, columns, instructions, template_version):
    """导入预检的公开响应。关联资料与日历文件家族共用；资源家族的 issue_preview 还要兼顾批量删除，不并进来。"""
    ref, expires_at = retain_context(PREVIEW_SCOPE, preview.document, content)
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
    from flask import request

    if (request.args or request.mimetype != "multipart/form-data" or set(request.files) != {"file"}
            or len(request.files.getlist("file")) != 1 or set(request.form) != {"format", "mode"}
            or any(len(request.form.getlist(key)) != 1 for key in request.form)):
        raise WorkbenchCommandRejected("invalid_input", "请上传一个文件并选好格式和导入方式；数据没有改动。选好后点「开始预检」。", 400)
    fmt, mode = request.form["format"], request.form["mode"]
    if fmt not in ("csv", "xlsx") or mode not in ("upsert",):
        raise WorkbenchCommandRejected("invalid_input", "只支持 CSV 或 XLSX 按编号增量导入；数据没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = read_upload_file("文件超过本机允许的大小，一行都没有导入。请缩小文件后重新选择，再点「开始预检」。")
    return content, fmt, mode


def download_args(required):
    from flask import request

    if set(request.args) != required or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "下载条件不完整或有多余项，没有开始下载。请刷新页面后重新点「导出」。", 400)
    fmt = request.args["format"]
    if fmt not in ("csv", "xlsx"):
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


def confirm_body():
    """确认导入的 JSON 请求体：只能确认刚预检过的那一批。"""
    from flask import g

    from core.models.workbench_command import validate_request_key

    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    opaque_ref(body["write_token"])
    if type(body["input"]) is not dict or set(body["input"]) != {"preview_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "只能确认刚才预检过的那一批，数据没有改动。请点「重新预检」。", 400)
    opaque_ref(body["input"]["preview_ref"])
    return body


def resolve_import_preview(ref, action, write_token):
    """按预检编号取回服务端留存的预检文档，并核对写令牌绑定的正是这一次操作。"""
    return _resolve_retained_preview(ref, action, write_token, "预检结果和这次操作对不上，数据没有改动。请点「重新预检」。")


def resolve_preview(ref, action, write_token):
    return _resolve_retained_preview(ref, action, write_token, "预检结果和这次操作或这条记录对不上，数据没有改动。请点「重新预检」。")


def _resolve_retained_preview(ref, action, write_token, message):
    from core.models.workbench_resource_action import ResourceActionPreview

    document, content = resolve_context(PREVIEW_SCOPE, ref, "stale_write")
    preview = ResourceActionPreview(document)
    if preview.as_dict()["operation"] != action:
        raise WorkbenchCommandRejected("stale_write", message)
    validate_preview_confirmation(write_token, ref)
    return preview, content
