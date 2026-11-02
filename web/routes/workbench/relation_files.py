"""可操作设备关系的文件路由。形状与资源文件家族一致，只是列目录和服务不同。"""

from __future__ import annotations

from flask import current_app, g, request

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_relation_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns, relation_kind
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.file_writer import check_capacity
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.relation_files.file_writer import write_relation_file
from core.services.workbench.resource.relation_files.files import WorkbenchRelationFileService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    EXPIRED_MESSAGE,
    EXPORT_SCOPE,
    IMPORT_MISMATCH_MESSAGE,
    PREVIEW_SCOPE,
    admit_export_selection,
    confirm_body,
    download_args,
    export_identity,
    file_response,
    issue_file_preview,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_context,
    retain_context,
    scope_input,
    upload_body,
)
from .write_context import resolve_action_preview

BASE = "/api/workbench/v1/relation-files"


def _reader():
    return WorkbenchResourceQueryService(g.db, "operator", current_app.logger)


def _service(kind):
    return WorkbenchRelationFileService(g.db, kind, current_app.logger)


@read_endpoint
def relation_import_preview(kind):
    relation_kind(kind)
    content, fmt, mode = upload_body()
    service = _service(kind)
    preview = service.preview_import(content, file_format=fmt, mode=mode)
    data = issue_file_preview(preview, columns=public_columns(kind),
                              instructions=INSTRUCTIONS, template_version=TEMPLATE_VERSION)
    snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import",
                                   "preview_ref": data["preview_ref"]}, data["preview_ref"])
    return query_success(data, snapshot, preview.as_dict()["notices"])


@api_endpoint
def relation_import_confirm(kind):
    relation_kind(kind)
    body = confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + ".import"
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_action_preview(PREVIEW_SCOPE, ref, operation, body["write_token"],
                                             expired_message=EXPIRED_MESSAGE, mismatch_message=IMPORT_MISMATCH_MESSAGE),
        mutate=lambda preview: _service(kind).confirm_import(preview))
    return json_response(outcome)


@read_endpoint
def relation_export_preview(kind):
    relation_kind(kind)
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    selection = admit_export_selection(
        body,
        message="请先选好导出全部、当前筛选还是选中的人员，没有开始下载。选好后重新点「导出」。",
    )
    page_request, query_scope, snapshot_ref = scope_input("operator", body)
    reader = _reader()
    with reader.read_snapshot() as fingerprint:
        read_binding = resolve_read_snapshot(snapshot_ref)
        snapshot = bind_read_snapshot(query_scope, fingerprint, snapshot_ref, binding=read_binding)
        service = WorkbenchRelationFileService(g.db, kind, current_app.logger, reader=reader)
        arguments, count = service.preview_export(selection, request=page_request, selected_refs=body.get("refs"))
        identity = export_identity(arguments)
        document = {"kind": kind, "query_scope": query_scope,
                    "snapshot_ref": snapshot_ref, "arguments": arguments, "row_count": count}
        ref, expires_at = retain_context(EXPORT_SCOPE, document, read_binding,
                                         key=(kind, read_binding.scope, document["snapshot_ref"], content_text(identity)))
    return query_success({"export_ref": ref, "expires_at": expires_at, "selection": selection,
                          "row_count": count, "scope": identity["scope"], "formats": FILE_FORMATS}, snapshot)


@read_endpoint
def relation_export(kind):
    relation_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"])
    binding, read_binding = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    reader = _reader()
    service = WorkbenchRelationFileService(g.db, kind, current_app.logger, reader=reader)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"], binding=read_binding)
        check_capacity(binding["row_count"], fmt)
        rows = service.export_rows(**binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(write_relation_file(kind, rows, fmt))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def relation_template(kind):
    relation_kind(kind)
    return file_response(write_relation_file(kind, [], download_args({"format"}), template=True))


def register_relation_file_routes(bp):
    bp.add_url_rule(BASE + "/<kind>/preview", view_func=relation_import_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/confirm", view_func=relation_import_confirm, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export-preview", view_func=relation_export_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export", view_func=relation_export, methods=["GET"])
    bp.add_url_rule(BASE + "/<kind>/template", view_func=relation_template, methods=["GET"])
