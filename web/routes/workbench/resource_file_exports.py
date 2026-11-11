"""Frozen scoped all/filtered/selected exports, independent from list pagination."""

from flask import current_app, g, request

from core.errors import ValidationError
from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import action_kind
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.facts.file_writer import write_resource_file
from core.services.workbench.resource.files import WorkbenchResourceFileService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from web.api_responses import query_success

from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    EXPORT_SCOPE,
    admit_export_selection,
    download_args,
    export_identity,
    file_response,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_context,
    retain_context,
    scope_input,
)


@read_endpoint
def resource_export_preview(kind):
    action_kind(kind)
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    selection = admit_export_selection(
        body,
        message="请先选好导出全部、当前筛选还是选中的记录，没有开始下载。选好后重新点「导出」。",
    )
    page_request, query_scope, snapshot_ref = scope_input(kind, body)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger, reader=reader)
    with reader.read_snapshot() as scope:
        read_binding = resolve_read_snapshot(snapshot_ref)
        snapshot = bind_read_snapshot(query_scope, scope.state_fingerprint(), snapshot_ref, binding=read_binding)
        arguments, count = service.preview_export(scope, selection, request=page_request, selected_refs=body.get("refs"))
        identity = export_identity(arguments)
        document = {"kind": kind, "query_scope": query_scope, "snapshot_ref": snapshot_ref, "arguments": arguments}
        ref, expires_at = retain_context(EXPORT_SCOPE, document, read_binding,
                                         key=(kind, read_binding.scope, document["snapshot_ref"], content_text(identity)))
    return query_success({"export_ref": ref, "expires_at": expires_at, "selection": selection,
                          "row_count": count, "scope": identity["scope"], "formats": FILE_FORMATS}, snapshot)


@read_endpoint
def resource_export(kind):
    action_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"])
    binding, read_binding = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger, reader=reader)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot(binding["query_scope"], scope.state_fingerprint(), binding["snapshot_ref"], binding=read_binding)
        rows = service.export_rows(scope, fmt, **binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(service.write_export(rows, fmt, request=binding["arguments"]["request"]))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def resource_template(kind):
    action_kind(kind)
    if kind != "op_type":
        return file_response(write_resource_file(kind, [], download_args({"format"}), template=True, category=None))
    fmt = download_args({"format", "category"})
    category = request.args["category"]
    if category not in ("internal", "external"):
        raise ValidationError("下载工种模板要先选自制还是外协，没有开始下载。请选好归属后重试。", field="category")
    return file_response(write_resource_file(kind, [], fmt, template=True, category=category))
