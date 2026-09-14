"""Frozen scoped all/filtered/selected exports, independent from list pagination."""

import json
from io import BytesIO

from flask import current_app, g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_resource_action import action_kind
from core.services.workbench.resource_files import WorkbenchResourceFileService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService

from .api_responses import query_success
from .read_context import bind_read_snapshot
from .resource_action_context import (
    EXPORT_SCOPE,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_context,
    retain_context,
    scope_input,
)


def _selection(kind, body, scope):
    selection = body["selection"]
    if selection not in ("all", "filtered", "selected") or ("refs" in body) != (selection == "selected"):
        raise WorkbenchCommandRejected("invalid_input", "请先选好导出全部、当前筛选还是选中的记录，没有开始下载。选好后重新点「导出」。", 400)
    service = WorkbenchResourceFileService(g.db, kind, current_app.logger)
    return service.preview_export(selection, scope=scope, selected_refs=body.get("refs"))


@read_endpoint
def resource_export_preview(kind):
    action_kind(kind)
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    scope, query_scope, snapshot_ref = scope_input(kind, body)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(query_scope, fingerprint, snapshot_ref)
        arguments, count = _selection(kind, body, scope)
        document = canonical_json({"kind": kind, "query_scope": query_scope, "snapshot_ref": snapshot_ref, "arguments": arguments})
        ref, expires_at = retain_context(EXPORT_SCOPE, document)
    return query_success({"export_ref": ref, "expires_at": expires_at, "selection": body["selection"],
                          "row_count": count, "scope": arguments["scope"], "formats": ["csv", "xlsx"]}, snapshot)


def _download_args(required):
    if set(request.args) != required or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "下载条件不完整或有多余项，没有开始下载。请刷新页面后重新点「导出」。", 400)
    fmt = request.args["format"]
    if fmt not in ("csv", "xlsx"):
        raise WorkbenchCommandRejected("invalid_input", "下载只支持 CSV 或 XLSX 格式，没有开始下载。请重新选择格式后点「导出」。", 400)
    return fmt


def _response(download):
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    return response


@read_endpoint
def resource_export(kind):
    action_kind(kind)
    fmt = _download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"], "export_ref")
    document, _ = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    binding = json.loads(document)
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"])
        download = WorkbenchResourceFileService(g.db, kind, current_app.logger).export(fmt, **binding["arguments"])
    response = _response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def resource_template(kind):
    action_kind(kind)
    fmt = _download_args({"format", "category"} if kind == "op_type" else {"format"})
    return _response(WorkbenchResourceFileService.template(kind, fmt, category=request.args.get("category")))
