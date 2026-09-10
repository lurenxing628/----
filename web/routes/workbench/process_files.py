"""Process imports retain original bytes; confirmation is one ordinary DB command."""

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import IMPORT_BYTE_LIMIT, check_format, file_columns
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_files import WorkbenchProcessFileService, file_operation
from core.services.workbench.process_queries import WorkbenchProcessQueryService

from .api_responses import api_endpoint, query_success
from .process_action_context import action_preview, checked_preview, confirmed_body
from .read_context import bind_read_snapshot
from .resource_action_context import read_endpoint


def _upload(kind):
    file_columns(kind)
    required, optional = {"format", "mode"}, {"target_ref"}
    if (request.args or request.mimetype != "multipart/form-data" or set(request.files) != {"file"}
            or len(request.files.getlist("file")) != 1 or not required <= set(request.form)
            or set(request.form) - required - optional or any(len(request.form.getlist(key)) != 1 for key in request.form)):
        raise WorkbenchCommandRejected("invalid_input", "请选择一个文件及明确的格式和导入方式。", 400)
    fmt, mode = request.form["format"], request.form["mode"]
    check_format(fmt)
    if mode != "upsert":
        raise WorkbenchCommandRejected("invalid_input", "工艺文件仅支持按图号增量导入。", 400)
    configured = current_app.config.get("EXCEL_MAX_UPLOAD_BYTES")
    limit = min(IMPORT_BYTE_LIMIT, configured) if type(configured) is int and configured > 0 else IMPORT_BYTE_LIMIT
    content = request.files["file"].read(limit + 1)
    if len(content) > limit:
        raise WorkbenchCommandRejected("invalid_input", "文件超过本机允许的大小，未截断或导入前半部分。", 413)
    return content, fmt, mode, request.form.get("target_ref")


@read_endpoint
def process_file_preview(kind):
    content, fmt, mode, target = _upload(kind)
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        preview, extra = WorkbenchProcessFileService(g.db, current_app.logger, reader).preview_import(
            kind, content, file_format=fmt, mode=mode, target_ref=target)
        data = action_preview(preview, file_operation(kind), kind=kind, content=content, extra=extra)
        snapshot = bind_read_snapshot({"kind": "process_file_import", "operation": file_operation(kind),
                                       "preview_ref": data["preview_ref"], "target_ref": target}, state)
    return query_success(data, snapshot)


@api_endpoint
def process_file_confirm(kind):
    operation = file_operation(kind)
    body = confirmed_body({"preview_ref", "discard_group_refs", "confirm_zero_unit_hours"})
    payload = body["input"]
    result = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=payload["preview_ref"], normalized_input=payload,
        guard=lambda: checked_preview(payload["preview_ref"], operation, operation, body["write_token"]),
        mutate=lambda checked: WorkbenchProcessFileService(g.db, current_app.logger).confirm_import(
            checked[0], checked[1], discard_group_refs=payload["discard_group_refs"],
            confirm_zero_unit_hours=payload["confirm_zero_unit_hours"]))
    return jsonify(result)


def register_process_file_routes(bp):
    from .process_file_exports import process_file_export, process_file_export_preview, process_file_template

    root = "/api/workbench/v1/process-files/<kind>"
    for path, view, method in (("preview", process_file_preview, "POST"), ("confirm", process_file_confirm, "POST"),
                               ("export-preview", process_file_export_preview, "POST"),
                               ("export", process_file_export, "GET"), ("template", process_file_template, "GET")):
        bp.add_url_rule(root + "/" + path, view_func=view, methods=[method])
