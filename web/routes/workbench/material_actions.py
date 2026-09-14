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

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_material_file import normalize_refs
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material_bulk import WorkbenchMaterialBulkService
from core.services.workbench.material_files import WorkbenchMaterialFileService
from core.services.workbench.material_queries import WorkbenchMaterialQueryService

from .api_responses import api_endpoint, query_success
from .material_actions_context import (
    check_source_snapshot,
    issue_preview,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_preview,
    scope_input,
)
from .read_context import bind_read_snapshot


@read_endpoint
def material_bulk_preview():
    body = json_body({"action", "refs", "scope", "snapshot_ref"}, {"page_size"})
    if body["action"] != "delete":
        raise WorkbenchCommandRejected("invalid_input", "批量操作只支持删除选中的物料，这次没有改动任何物料。请先勾选要删除的物料。", 400)
    refs = normalize_refs(body["refs"])
    scope, query_scope, token = scope_input(body)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = check_source_snapshot(query_scope, fingerprint, token)
        preview = WorkbenchMaterialBulkService(g.db, current_app.logger).preview_delete(refs, scope=scope)
        data = issue_preview(preview)
    return query_success(data, snapshot)


def _upload():
    if request.args or request.mimetype != "multipart/form-data":
        raise WorkbenchCommandRejected("invalid_input", "没有收到上传的文件，物料没有改动。请重新选择文件后点「开始预检」。", 400)
    if (set(request.files) != {"file"} or len(request.files.getlist("file")) != 1
            or set(request.form) != {"format", "mode"}
            or any(len(request.form.getlist(key)) != 1 for key in request.form)):
        raise WorkbenchCommandRejected("invalid_input", "一次只能上传一个文件，并且要选好格式和导入方式；物料没有改动。请重新选择后点「开始预检」。", 400)
    file_format, mode = request.form["format"], request.form["mode"]
    if file_format not in ("csv", "xlsx") or mode != "upsert":
        raise WorkbenchCommandRejected("invalid_input", "物料导入只支持 CSV 或 XLSX，并且按物料编号增量更新；物料没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = request.files["file"].read()
    limit = int(current_app.config.get("EXCEL_MAX_UPLOAD_BYTES") or current_app.config.get("MAX_CONTENT_LENGTH") or 0)
    if limit > 0 and len(content) > limit:
        raise WorkbenchCommandRejected("invalid_input", "文件超过本机允许的大小，一行都没有导入，也没有只导入前半部分。请缩小文件后重新点「开始预检」。", 413)
    return content, file_format, mode


@read_endpoint
def material_import_preview():
    content, file_format, mode = _upload()
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        preview = WorkbenchMaterialFileService(g.db, current_app.logger).preview_import(
            content, file_format=file_format, mode=mode, scope={})
        data = issue_preview(preview, content)
        snapshot = bind_read_snapshot({"kind": "material", "operation": "material.import",
                                       "preview_ref": data["preview_ref"]}, fingerprint)
    return query_success(data, snapshot)


def _confirm_body():
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    opaque_ref(body["write_token"], "write_token")
    if type(body["input"]) is not dict or set(body["input"]) != {"preview_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "只能确认刚才预检过的那一批，物料没有改动。请重新点「开始预检」。", 400)
    opaque_ref(body["input"]["preview_ref"], "preview_ref")
    return body


def _apply_preview(action, checked):
    preview, content = checked
    original = preview.as_dict()["request"]
    if action == "material.bulk_delete":
        return WorkbenchMaterialBulkService(g.db, current_app.logger).confirm_delete(
            preview, original["refs"], scope=original["scope"])
    return WorkbenchMaterialFileService(g.db, current_app.logger).confirm_import(
        preview, content, file_format=original["format"], mode=original["mode"], scope=original["scope"])


@api_endpoint
def material_action_confirm(action):
    body = _confirm_body()
    ref = body["input"]["preview_ref"]
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=action, context_ref=ref,
        normalized_input={"preview_ref": ref},
        guard=lambda: resolve_preview(ref, action, body["write_token"]),
        mutate=lambda checked: _apply_preview(action, checked))
    return jsonify(outcome)


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
