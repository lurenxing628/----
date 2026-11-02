"""Register resource batch routes only; global blueprint mounting belongs to the host."""

from flask import current_app, g

from core.models.workbench_action_values import UPSERT_IMPORT_MODES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import action_kind
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.bulk import WorkbenchResourceBulkService
from core.services.workbench.resource.files import WorkbenchResourceFileService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .request_json import read_upload_file, read_upload_form
from .resource_action_context import (
    EXPIRED_MESSAGE,
    PREVIEW_SCOPE,
    confirm_body,
    issue_preview,
    json_body,
    read_endpoint,
    scope_input,
)
from .write_context import resolve_action_preview

_MISMATCH_MESSAGE = "预检结果和这次操作或这条记录对不上，数据没有改动。请点「重新预检」。"


@read_endpoint
def resource_bulk_preview(kind):
    action_kind(kind)
    body = json_body({"action", "refs", "scope", "snapshot_ref"}, {"page_size"})
    if body["action"] != "delete":
        raise WorkbenchCommandRejected("invalid_input", "批量操作只支持删除选中的记录，这次没有改动任何记录。请先勾选要删除的记录。", 400)
    page_request, query_scope, token = scope_input(kind, body)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(query_scope, fingerprint, token)
        preview = WorkbenchResourceBulkService(g.db, kind, current_app.logger, reader=reader).preview_delete(body["refs"], scope=page_request)
        data = issue_preview(kind, preview)
    return query_success(data, snapshot)


def _upload(kind):
    shape = "请上传一个文件并选好格式和导入方式，工种还要选自制或外协；数据没有改动。选好后点「开始预检」。"
    form = read_upload_form({"format", "mode"} | ({"category"} if kind == "op_type" else set()), transport=shape, shape=shape)
    fmt, mode = form["format"], form["mode"]
    category = form.get("category")
    if fmt not in FILE_FORMATS or mode not in UPSERT_IMPORT_MODES or (kind == "op_type" and category not in ("internal", "external")):
        raise WorkbenchCommandRejected("invalid_input", "只支持 CSV 或 XLSX 按编号增量导入，工种还要选自制或外协；数据没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = read_upload_file("文件超过本机允许的大小，一行都没有导入。请缩小文件后重新点「开始预检」。")
    return content, fmt, mode, category


@read_endpoint
def resource_import_preview(kind):
    action_kind(kind)
    content, fmt, mode, category = _upload(kind)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger)
    preview = service.preview_import(content, file_format=fmt, mode=mode, category=category)
    data = issue_preview(kind, preview)
    scope = {"category": category} if kind == "op_type" else {}
    snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import", "preview_ref": data["preview_ref"], **scope}, data["preview_ref"])
    return query_success(data, snapshot, preview.as_dict()["notices"])


def _apply(kind, action, preview):
    if action == "bulk_delete":
        return WorkbenchResourceBulkService(g.db, kind, current_app.logger).confirm_delete(preview)
    return WorkbenchResourceFileService(g.db, kind, current_app.logger).confirm_import(preview)


@api_endpoint
def resource_action_confirm(kind, action):
    action_kind(kind)
    body = confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + "." + action
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_action_preview(PREVIEW_SCOPE, ref, operation, body["write_token"], expired_message=EXPIRED_MESSAGE,
                                             mismatch_message=_MISMATCH_MESSAGE),
        mutate=lambda preview: _apply(kind, action, preview))
    return json_response(outcome)


def register_resource_action_routes(bp):
    from .operator_machine_permissions import register_operator_machine_routes
    from .resource_file_exports import resource_export, resource_export_preview, resource_template

    register_operator_machine_routes(bp)

    base = "/api/workbench/v1"
    bp.add_url_rule(base + "/entities/<kind>/bulk-preview", view_func=resource_bulk_preview, methods=["POST"])
    bp.add_url_rule(base + "/imports/<kind>/preview", view_func=resource_import_preview, methods=["POST"])
    for path, action in (("/entities/<kind>/bulk-confirm", "bulk_delete"), ("/imports/<kind>/confirm", "import")):
        bp.add_url_rule(base + path, endpoint="resource_" + action + "_confirm", view_func=resource_action_confirm,
                        defaults={"action": action}, methods=["POST"])
    bp.add_url_rule(base + "/exports/<kind>/preview", view_func=resource_export_preview, methods=["POST"])
    bp.add_url_rule(base + "/exports/<kind>", view_func=resource_export, methods=["GET"])
    bp.add_url_rule(base + "/templates/<kind>", view_func=resource_template, methods=["GET"])
