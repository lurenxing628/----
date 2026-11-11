"""Material bulk/import HTTP entry points; register_material_action_routes(bp).

All paths start /api/workbench/v1. Previews are read-only QuerySuccess values:
  POST entities/material/bulk-preview:
    {action:'delete', refs:[EntityRef], scope:{query?,status?,sort?,direction?},
     snapshot_ref:<list meta.snapshot_ref>, page_size?:20}
  POST imports/material/preview: multipart file, format=csv|xlsx, mode=upsert.
  POST entities/material/bulk-confirm or imports/material/confirm:
    {request_key, write_token:<preview write_context.write_token>, input:{preview_ref}}

Confirmation accepts no client facts. Its normalized intent is the opaque,
immutable server preview reference. CommandService compares that intent and
action before resolving any expiring token, so committed requests still replay
after expiry/restart. The guard resolves the canonical preview and write context;
the domain mutation revalidates every original fact under the same transaction.
"""

from __future__ import annotations

from flask import current_app, g

from core.models.workbench_action_values import UPSERT_IMPORT_MODES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material.bulk import WorkbenchMaterialBulkService
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .material_actions_context import (
    EXPIRED_MESSAGE,
    PREVIEW_SCOPE,
    issue_preview,
    json_body,
    read_endpoint,
    scope_input,
)
from .read_context import bind_read_snapshot
from .request_json import read_upload_file, read_upload_form
from .resource_action_context import confirm_body
from .write_context import resolve_action_preview


@read_endpoint
def material_bulk_preview():
    body = json_body({"action", "refs", "scope", "snapshot_ref"}, {"page_size"})
    if body["action"] != "delete":
        raise WorkbenchCommandRejected("invalid_input", "批量操作只支持删除选中的物料，这次没有改动任何物料。请先勾选要删除的物料。", 400)
    page_request, query_scope, token = scope_input(body)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot(query_scope, scope.state_fingerprint(), token)
        preview = WorkbenchMaterialBulkService(g.db, current_app.logger).preview_delete(
            body["refs"], scope=page_request)
        data = issue_preview(preview)
    return query_success(data, snapshot)


def _upload():
    form = read_upload_form({"format", "mode"}, transport="没有收到上传的文件，物料没有改动。请重新选择文件后点「开始预检」。",
                            shape="一次只能上传一个文件，并且要选好格式和导入方式；物料没有改动。请重新选择后点「开始预检」。")
    file_format, mode = form["format"], form["mode"]
    if file_format not in FILE_FORMATS or mode not in UPSERT_IMPORT_MODES:
        raise WorkbenchCommandRejected("invalid_input", "物料导入只支持 CSV 或 XLSX，并且按物料编号增量更新；物料没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = read_upload_file("文件超过本机允许的大小，一行都没有导入，也没有只导入前半部分。请缩小文件后重新点「开始预检」。")
    return content, file_format, mode


@read_endpoint
def material_import_preview():
    content, file_format, mode = _upload()
    service = WorkbenchMaterialFileService(g.db, current_app.logger)
    preview = service.preview_import(content, file_format=file_format, mode=mode)
    data = issue_preview(preview)
    snapshot = bind_read_snapshot({"kind": "material", "operation": "material.import",
                                   "preview_ref": data["preview_ref"]}, data["preview_ref"])
    return query_success(data, snapshot, preview.as_dict()["notices"])


def _apply_preview(action, preview):
    if action == "material.bulk_delete":
        return WorkbenchMaterialBulkService(g.db, current_app.logger).confirm_delete(preview)
    return WorkbenchMaterialFileService(g.db, current_app.logger).confirm_import(preview)


@api_endpoint
def material_action_confirm(action):
    body = confirm_body("只能确认刚才预检过的那一批，物料没有改动。请点「重新预检」。")
    ref = body["input"]["preview_ref"]
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=action, context_ref=ref,
        normalized_input={"preview_ref": ref},
        guard=lambda: resolve_action_preview(
            PREVIEW_SCOPE, ref, action, body["write_token"], expired_message=EXPIRED_MESSAGE,
            mismatch_message="预检结果不适用于这次操作，物料没有改动。请点「重新预检」。"),
        mutate=lambda preview: _apply_preview(action, preview))
    return json_response(outcome)


def register_material_action_routes(bp):
    from .material_actions_export import material_export, material_export_preview, material_template

    base = "/api/workbench/v1"
    bp.add_url_rule(base + "/entities/material/bulk-preview", view_func=material_bulk_preview, methods=["POST"])
    bp.add_url_rule(base + "/imports/material/preview", view_func=material_import_preview, methods=["POST"])
    for path, action in (("/entities/material/bulk-confirm", "material.bulk_delete"),
                         ("/imports/material/confirm", "material.import")):
        bp.add_url_rule(base + path, endpoint=action.replace(".", "_") + "_confirm", view_func=material_action_confirm,
                        defaults={"action": action}, methods=["POST"])
    bp.add_url_rule(base + "/exports/material/preview", view_func=material_export_preview, methods=["POST"])
    bp.add_url_rule(base + "/exports/material", view_func=material_export, methods=["GET"])
    bp.add_url_rule(base + "/templates/material", view_func=material_template, methods=["GET"])
