"""Process imports retain parsed file facts; confirmation rechecks current DB facts."""

from flask import current_app, g

from core.models.workbench_action_values import UPSERT_IMPORT_MODES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_file import check_format, file_columns
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process import scope as process_scope
from core.services.workbench.process.files import WorkbenchProcessFileService, file_operation
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .process_action_context import action_preview, checked_preview, confirmed_body
from .read_context import bind_read_snapshot
from .request_json import read_upload_file, read_upload_form
from .resource_action_context import read_endpoint


def _upload(kind):
    file_columns(kind)
    shape = "请先选好文件、格式和导入方式，工艺资料没有改动。选好后点「开始预检」。"
    form = read_upload_form({"format", "mode"}, optional={"target_ref"}, transport=shape, shape=shape)
    fmt, mode = form["format"], form["mode"]
    check_format(fmt)
    if mode not in UPSERT_IMPORT_MODES:
        raise WorkbenchCommandRejected("invalid_input", "工艺文件只支持按图号增量导入，工艺资料没有改动。请换用正确的导入方式后点「开始预检」。", 400)
    target = form.get("target_ref")
    if target is not None:
        process_scope.check_part_ref(target)
    content = read_upload_file("文件超过本机允许的大小，一行都没有导入，也没有只导入前半部分。请缩小文件后重新选择，再点「开始预检」。")
    return content, fmt, mode, target


@read_endpoint
def process_file_preview(kind):
    content, fmt, mode, target = _upload(kind)
    service = WorkbenchProcessFileService(g.db, current_app.logger)
    # 文件事实只解析、校验一次；每次预检仍在服务读快照中比对当前工艺资料。
    preview, extra = service.preview_import(kind, content, file_format=fmt, mode=mode, target_ref=target)
    body = preview.as_dict()
    data = action_preview(preview, body["operation"], kind=kind, extra=extra)
    snapshot = bind_read_snapshot({"kind": "process_file_import", "operation": body["operation"],
                                   "preview_ref": data["preview_ref"], "target_ref": target}, body["request"]["state"])
    return query_success(data, snapshot, body["notices"])


@api_endpoint
def process_file_confirm(kind):
    file_columns(kind)
    operation = file_operation(kind)
    body = confirmed_body({"preview_ref", "discard_group_refs", "confirm_zero_unit_hours"})
    payload = body["input"]
    result = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=payload["preview_ref"], normalized_input=payload,
        guard=lambda: checked_preview(payload["preview_ref"], operation, body["write_token"]),
        mutate=lambda preview: WorkbenchProcessFileService(g.db, current_app.logger).confirm_import(
            preview, discard_group_refs=payload["discard_group_refs"],
            confirm_zero_unit_hours=payload["confirm_zero_unit_hours"]))
    return json_response(result)


def register_process_file_routes(bp):
    from .process_file_exports import process_file_export, process_file_export_preview, process_file_template

    root = "/api/workbench/v1/process-files/<kind>"
    for path, view, method in (("preview", process_file_preview, "POST"), ("confirm", process_file_confirm, "POST"),
                               ("export-preview", process_file_export_preview, "POST"),
                               ("export", process_file_export, "GET"), ("template", process_file_template, "GET")):
        bp.add_url_rule(root + "/" + path, view_func=view, methods=[method])
