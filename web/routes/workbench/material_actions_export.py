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

from io import BytesIO

from flask import current_app, g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_file import normalize_refs, normalize_scope
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.material_files import WorkbenchMaterialFileService
from core.services.workbench.material_queries import WorkbenchMaterialQueryService

from .api_responses import query_success
from .material_actions_context import (
    EXPORT_SCOPE,
    check_source_snapshot,
    issue_binding,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_binding,
    scope_input,
)


def _selection(body, reader, scope):
    selected = body["selection"]
    if selected not in ("all", "filtered", "selected") or ("refs" in body) != (selected == "selected"):
        raise WorkbenchCommandRejected("invalid_input", "导出范围必须明确为全部、当前筛选或选中项；仅选中项可提供refs。", 400)
    if selected == "selected":
        refs = normalize_refs(body["refs"], allow_empty=True)
        for ref in refs:
            reader.detail(ref)
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
        snapshot = check_source_snapshot(query_scope, fingerprint, snapshot_ref)
        arguments, count = _selection(body, reader, scope)
        binding = {"version": 1, "source": "production", "query_scope": query_scope,
                   "snapshot_ref": snapshot_ref, "arguments": arguments}
        ref, expires_at = issue_binding(EXPORT_SCOPE, binding)
    data = {"export_ref": ref, "expires_at": expires_at, "selection": body["selection"],
            "row_count": count, "scope": arguments.get("scope"), "formats": ["csv", "xlsx"]}
    return query_success(data, snapshot)


def _download_args(required):
    if set(request.args) != set(required) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "下载参数缺失、重复或包含不支持的字段。", 400)
    file_format = request.args["format"]
    if file_format not in ("csv", "xlsx"):
        raise WorkbenchCommandRejected("invalid_input", "下载格式只支持CSV或XLSX。", 400)
    return file_format


def _download_response(download):
    response = send_file(BytesIO(download.content), mimetype=download.mime_type,
                         as_attachment=True, download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    return response


@read_endpoint
def material_export():
    file_format = _download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"], "export_ref")
    binding = resolve_binding(EXPORT_SCOPE, ref, field="export_ref", code="snapshot_stale")
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = check_source_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"])
        download = WorkbenchMaterialFileService(g.db, current_app.logger).export(file_format, **binding["arguments"])
    response = _download_response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def material_template():
    file_format = _download_args({"format"})
    return _download_response(WorkbenchMaterialFileService.template(file_format))
