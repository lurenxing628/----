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

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_file import normalize_refs, normalize_scope
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material.files import WorkbenchMaterialFileService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from web.api_responses import query_success

from .material_actions_context import (
    EXPORT_SCOPE,
    issue_binding,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_binding,
    scope_input,
)
from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import download_args, file_response


def _selection(body, reader, scope):
    selected = body["selection"]
    if selected not in ("all", "filtered", "selected") or ("refs" in body) != (selected == "selected"):
        raise WorkbenchCommandRejected("invalid_input", "请先选好导出全部、当前筛选还是选中的物料，没有开始下载。选好后重新点「导出」。", 400)
    if selected == "selected":
        refs = normalize_refs(body["refs"], allow_empty=True)
        for ref in refs:
            reader.resolve(ref)
        return {"selected_refs": refs}, len(refs)
    effective = normalize_scope({}) if selected == "all" else scope
    _, page = reader.page(MaterialPageRequest(**effective, size=1))
    return {"scope": effective}, page["total"]


@read_endpoint
def material_export_preview():
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    scope, query_scope, snapshot_ref = scope_input(body)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        read_binding = resolve_read_snapshot(snapshot_ref)
        snapshot = bind_read_snapshot(query_scope, fingerprint, snapshot_ref, binding=read_binding)
        arguments, count = _selection(body, reader, scope)
        binding = {"query_scope": query_scope, "snapshot_ref": snapshot_ref,
                   "read_binding": read_binding, "arguments": arguments}
        ref, expires_at = issue_binding(EXPORT_SCOPE, binding)
    data = {"export_ref": ref, "expires_at": expires_at, "selection": body["selection"],
            "row_count": count, "scope": arguments.get("scope"), "formats": ["csv", "xlsx"]}
    return query_success(data, snapshot)


@read_endpoint
def material_export():
    file_format = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"])
    binding = resolve_binding(EXPORT_SCOPE, ref, field="export_ref", code="snapshot_stale")
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"], binding=binding["read_binding"])
        rows = WorkbenchMaterialFileService(g.db, current_app.logger, reader=reader).export_rows(file_format, **binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(WorkbenchMaterialFileService.write_export(rows, file_format))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def material_template():
    file_format = download_args({"format"})
    return file_response(WorkbenchMaterialFileService.template(file_format))
