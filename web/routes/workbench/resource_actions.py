"""Register resource batch routes only; global blueprint mounting belongs to the host."""

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_resource_action import action_kind, resource_refs
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource_bulk import WorkbenchResourceBulkService
from core.services.workbench.resource_files import WorkbenchResourceFileService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .resource_action_context import issue_preview, json_body, opaque_ref, read_endpoint, resolve_preview, scope_input


@read_endpoint
def resource_bulk_preview(kind):
    action_kind(kind)
    body = json_body({"action", "refs", "scope", "snapshot_ref"}, {"page_size"})
    if body["action"] != "delete":
        raise WorkbenchCommandRejected("invalid_input", "批量操作只支持删除选中的记录，这次没有改动任何记录。请先勾选要删除的记录。", 400)
    refs = resource_refs(body["refs"])
    scope, query_scope, token = scope_input(kind, body)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(query_scope, fingerprint, token)
        preview = WorkbenchResourceBulkService(g.db, kind, current_app.logger).preview_delete(refs, scope=scope)
        data = issue_preview(kind, preview)
    return query_success(data, snapshot)


def _upload_shape(kind):
    required = {"format", "mode"} | ({"category"} if kind == "op_type" else set())
    if (request.args or request.mimetype != "multipart/form-data" or set(request.files) != {"file"}
            or len(request.files.getlist("file")) != 1 or set(request.form) != required
            or any(len(request.form.getlist(key)) != 1 for key in request.form)):
        raise WorkbenchCommandRejected("invalid_input", "请上传一个文件并选好格式和导入方式，工种还要选自制或外协；数据没有改动。选好后点「开始预检」。", 400)


def _upload(kind):
    _upload_shape(kind)
    fmt, mode = request.form["format"], request.form["mode"]
    category = request.form.get("category")
    if fmt not in ("csv", "xlsx") or mode != "upsert" or (kind == "op_type" and category not in ("internal", "external")):
        raise WorkbenchCommandRejected("invalid_input", "只支持 CSV 或 XLSX 按编号增量导入，工种还要选自制或外协；数据没有改动。请换用正确的文件后点「开始预检」。", 400)
    content = request.files["file"].read()
    limit = int(current_app.config.get("EXCEL_MAX_UPLOAD_BYTES") or current_app.config.get("MAX_CONTENT_LENGTH") or 0)
    if limit > 0 and len(content) > limit:
        raise WorkbenchCommandRejected("invalid_input", "文件超过本机允许的大小，一行都没有导入。请缩小文件后重新点「开始预检」。", 413)
    return content, fmt, mode, {"category": category} if kind == "op_type" else {}


@read_endpoint
def resource_import_preview(kind):
    action_kind(kind)
    content, fmt, mode, scope = _upload(kind)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        preview = WorkbenchResourceFileService(g.db, kind, current_app.logger).preview_import(content, file_format=fmt, mode=mode, scope=scope)
        data = issue_preview(kind, preview, content)
        snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import", "preview_ref": data["preview_ref"], **scope}, fingerprint)
    return query_success(data, snapshot)


def _confirm_body():
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    opaque_ref(body["write_token"], "write_token")
    if type(body["input"]) is not dict or set(body["input"]) != {"preview_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "只能确认刚才预检过的那一批，数据没有改动。请重新点「开始预检」。", 400)
    opaque_ref(body["input"]["preview_ref"], "preview_ref")
    return body


def _apply(kind, action, checked):
    preview, content = checked
    original = preview.as_dict()["request"]
    if action == "bulk_delete":
        return WorkbenchResourceBulkService(g.db, kind, current_app.logger).confirm_delete(preview, original["refs"], scope=original["scope"])
    return WorkbenchResourceFileService(g.db, kind, current_app.logger).confirm_import(
        preview, content, file_format=original["format"], mode=original["mode"], scope=original["scope"])


@api_endpoint
def resource_action_confirm(kind, action):
    action_kind(kind)
    body = _confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + "." + action
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_preview(ref, operation, body["write_token"]), mutate=lambda checked: _apply(kind, action, checked))
    return jsonify(outcome)


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
