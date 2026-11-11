"""Read-only export scope approval and complete CSV/XLSX downloads.

POST /api/workbench/v1/exports/material/preview accepts
{selection:'all'|'filtered'|'selected', scope, snapshot_ref, page_size?:20, refs?}.
refs is required only for selected; [] explicitly means an empty export.
scope/page_size/snapshot_ref describe the currently viewed list. 'all' explicitly
exports the full collection; 'filtered' exports all matches; 'selected' preserves
the entire ordered selection including hidden rows. Returns export_ref, row_count,
selection, effective scope, expiry and snapshot metadata. GET exports/material
accepts only export_ref and format. No filter, ref list or path can override it.
"""

from __future__ import annotations

from flask import current_app, g, request

from core.models.content import content_text
from core.models.workbench_material_file import normalize_refs, wire_scope
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.material.file_codec import write_material_file
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from web.api_responses import query_success

from .material_actions_context import (
    EXPIRED_MESSAGE,
    EXPORT_SCOPE,
    json_body,
    opaque_ref,
    read_endpoint,
    scope_input,
)
from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    admit_export_selection,
    download_args,
    file_response,
    resolve_context,
    retain_context,
)


def _selection(body, scope, request):
    """The export's arguments (a validated request or explicit refs), their public scope and row count."""
    selected = admit_export_selection(
        body,
        message="请先选好导出全部、当前筛选还是选中的物料，没有开始下载。选好后重新点「导出」。",
    )
    if selected == "selected":
        refs = normalize_refs(body["refs"], allow_empty=True)
        scope.resolve_many(refs)
        return {"selected_refs": refs}, None, len(refs)
    effective = MaterialPageRequest() if selected == "all" else request
    return {"request": effective}, wire_scope(effective), scope.count(effective)


@read_endpoint
def material_export_preview():
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    page_request, query_scope, snapshot_ref = scope_input(body)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fact_scope:
        read_binding = resolve_read_snapshot(snapshot_ref)
        snapshot = bind_read_snapshot(query_scope, fact_scope.state_fingerprint(), snapshot_ref, binding=read_binding)
        arguments, scope, count = _selection(body, fact_scope, page_request)
        document = {"query_scope": query_scope, "snapshot_ref": snapshot_ref, "arguments": arguments}
        identity = {"selected_refs": arguments["selected_refs"]} if scope is None else {"scope": scope}
        ref, expires_at = retain_context(
            EXPORT_SCOPE,
            document,
            read_binding,
            key=(read_binding.scope, snapshot_ref, content_text(identity)),
        )
    data = {"export_ref": ref, "expires_at": expires_at, "selection": body["selection"],
            "row_count": count, "scope": scope, "formats": FILE_FORMATS}
    return query_success(data, snapshot)


@read_endpoint
def material_export():
    file_format = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"])
    binding, read_binding = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale", expired_message=EXPIRED_MESSAGE)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot(
            binding["query_scope"],
            scope.state_fingerprint(),
            binding["snapshot_ref"],
            binding=read_binding,
        )
        rows = WorkbenchMaterialFileService(g.db, current_app.logger).export_rows(scope, file_format, **binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(write_material_file(rows, file_format))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def material_template():
    file_format = download_args({"format"})
    return file_response(write_material_file([], file_format, template=True))
