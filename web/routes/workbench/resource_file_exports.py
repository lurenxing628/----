"""Frozen scoped all/filtered/selected exports, independent from list pagination."""

from flask import current_app, g, request

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import action_kind
from core.services.workbench.resource.files import WorkbenchResourceFileService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from web.api_responses import query_success

from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    EXPORT_SCOPE,
    download_args,
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
    selection = body["selection"]
    if selection not in ("all", "filtered", "selected") or ("refs" in body) != (selection == "selected"):
        raise WorkbenchCommandRejected("invalid_input", "请先选好导出全部、当前筛选还是选中的记录，没有开始下载。选好后重新点「导出」。", 400)
    scope, query_scope, snapshot_ref = scope_input(kind, body)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger, reader=reader)
    with reader.read_snapshot() as fingerprint:
        read_binding = resolve_read_snapshot(snapshot_ref)
        snapshot = bind_read_snapshot(query_scope, fingerprint, snapshot_ref, binding=read_binding)
        arguments, count = service.preview_export(selection, scope=scope, selected_refs=body.get("refs"))
        document = {"kind": kind, "query_scope": query_scope, "snapshot_ref": snapshot_ref, "arguments": arguments}
        ref, expires_at = retain_context(EXPORT_SCOPE, document, read_binding,
                                         key=(kind, read_binding.scope, document["snapshot_ref"], content_text(arguments)))
    return query_success({"export_ref": ref, "expires_at": expires_at, "selection": selection,
                          "row_count": count, "scope": arguments["scope"], "formats": ["csv", "xlsx"]}, snapshot)


@read_endpoint
def resource_export(kind):
    action_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"], "export_ref")
    binding, read_binding = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger, reader=reader)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"], binding=read_binding)
        rows = service.export_rows(fmt, **binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(service.write_export(rows, fmt, scope=binding["arguments"]["scope"]))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def resource_template(kind):
    action_kind(kind)
    fmt = download_args({"format", "category"} if kind == "op_type" else {"format"})
    return file_response(WorkbenchResourceFileService.template(kind, fmt, category=request.args.get("category")))
