"""Download exactly the preflighted process scope, format and read snapshot."""

import json

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_process_file import check_format, file_columns, public_columns
from core.services.workbench.process_file_codec import encode_process_file
from core.services.workbench.process_file_export import (
    count_process_export_rows,
    process_export_rows,
    select_export_parts,
)
from core.services.workbench.process_queries import WorkbenchProcessQueryService

from .api_responses import query_success
from .material_actions_context import opaque_ref
from .process_action_context import EXPORT_SCOPE
from .process_collections import collection_scope
from .process_json import read_process_json
from .read_context import bind_read_snapshot
from .resource_action_context import read_endpoint, resolve_context, retain_context
from .resource_file_exports import _response


def _query_scope(body):
    scope = body["scope"]
    _, query_scope = collection_scope(scope, body["page_size"])
    if "target_ref" in body:
        if scope:
            raise WorkbenchCommandRejected("invalid_input", "当前详情导出不接受其他筛选范围。", 400)
        query_scope = {"kind": "part", "entity_ref": body["target_ref"]}
    return query_scope


@read_endpoint
def process_file_export_preview(kind):
    file_columns(kind)
    body = read_process_json("工艺文件导出", 16 * 1024 * 1024)
    required = {"format", "selection", "scope", "snapshot_ref", "page_size"}
    if not required <= set(body) or set(body) - required - {"refs", "target_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "工艺导出范围不完整或包含未知字段。", 400)
    if ("refs" in body) != (body["selection"] == "explicit"):
        raise WorkbenchCommandRejected("invalid_input", "只有明确选中项接受 refs，不能用空值代替未提供的选择。", 400)
    check_format(body["format"])
    token = opaque_ref(body["snapshot_ref"], "snapshot_ref")
    query_scope = _query_scope(body)
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query_scope, state, token)
        parts, scope = select_export_parts(reader, selection=body["selection"], scope=body["scope"],
                                          refs=body.get("refs"), target_ref=body.get("target_ref"))
        count = count_process_export_rows(kind, parts, reader.facts(), body["format"])
        document = canonical_json({"kind": kind, "body": body, "query_scope": query_scope,
                                   "state": state, "row_count": count, "part_count": len(parts)})
        ref, expiry = retain_context(EXPORT_SCOPE, document)
    return query_success({"kind": kind, "export_ref": ref, "expires_at": expiry, "selection": body["selection"],
                          "scope": scope, "target_ref": body.get("target_ref"), "row_count": count,
                          "part_count": len(parts), "format": body["format"], "columns": public_columns(kind)}, snapshot)


def _args(required):
    if set(request.args) != required or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "下载参数缺失、重复或包含未知字段。", 400)


@read_endpoint
def process_file_export(kind):
    file_columns(kind)
    _args({"export_ref"})
    document, _ = resolve_context(EXPORT_SCOPE, opaque_ref(request.args["export_ref"], "export_ref"), "snapshot_stale")
    saved = json.loads(document)
    if saved["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "原预检属于另一类工艺文件，未切换下载内容。")
    body = saved["body"]
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(saved["query_scope"], state, body["snapshot_ref"])
        if state != saved["state"]:
            raise WorkbenchCommandRejected("snapshot_stale", "原导出资料已变化，请重新预检。")
        parts, _ = select_export_parts(reader, selection=body["selection"], scope=body["scope"],
                                      refs=body.get("refs"), target_ref=body.get("target_ref"))
        download = encode_process_file(kind, process_export_rows(kind, parts, reader.facts()), body["format"])
        if download.row_count != saved["row_count"] or len(parts) != saved["part_count"]:
            raise WorkbenchCommandRejected("snapshot_stale", "原导出范围记录数已变化，未下载部分内容。")
    response = _response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def process_file_template(kind):
    file_columns(kind)
    _args({"format"})
    return _response(encode_process_file(kind, [], request.args["format"]))
