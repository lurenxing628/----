"""可操作设备关系的文件路由。形状与资源文件家族一致，只是列目录和服务不同。"""

import json

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.models.workbench_relation_file import INSTRUCTIONS, TEMPLATE_VERSION, public_columns, relation_kind
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.services.workbench.resource.relation_files.files import WorkbenchRelationFileService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .resource_action_context import (
    EXPORT_SCOPE,
    confirm_body,
    download_args,
    file_response,
    issue_file_preview,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_context,
    resolve_import_preview,
    retain_context,
    scope_input,
    upload_body,
)

BASE = "/api/workbench/v1/relation-files"


def _reader():
    return WorkbenchResourceQueryService(g.db, "operator", current_app.logger)


def _service(kind):
    return WorkbenchRelationFileService(g.db, kind, current_app.logger)


@read_endpoint
def relation_import_preview(kind):
    relation_kind(kind)
    content, fmt, mode = upload_body()
    reader = _reader()
    service = _service(kind)
    source = service.prepare_import(content, file_format=fmt, mode=mode)
    with reader.read_snapshot(capture_fingerprint=False):
        preview = service.preview_import(source, file_format=fmt, mode=mode)
        data = issue_file_preview(preview, source, columns=public_columns(kind),
                                  instructions=INSTRUCTIONS, template_version=TEMPLATE_VERSION)
        snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import",
                                       "preview_ref": data["preview_ref"]}, data["preview_ref"])
    return query_success(data, snapshot, preview.as_dict()["notices"])


def _apply(kind, checked):
    preview, content = checked
    original = preview.as_dict()["request"]
    return _service(kind).confirm_import(preview, content, file_format=original["format"], mode=original["mode"])


@api_endpoint
def relation_import_confirm(kind):
    relation_kind(kind)
    body = confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + ".import"
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_import_preview(ref, operation, body["write_token"]),
        mutate=lambda checked: _apply(kind, checked))
    return jsonify(outcome)


@read_endpoint
def relation_export_preview(kind):
    relation_kind(kind)
    body = json_body({"selection", "scope", "snapshot_ref"}, {"refs", "page_size"})
    if body["selection"] not in ("all", "filtered", "selected") or ("refs" in body) != (body["selection"] == "selected"):
        raise WorkbenchCommandRejected("invalid_input", "请先选好导出全部、当前筛选还是选中的人员，没有开始下载。选好后重新点「导出」。", 400)
    scope, query_scope, snapshot_ref = scope_input("operator", body)
    reader = _reader()
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(query_scope, fingerprint, snapshot_ref)
        arguments, count = _service(kind).preview_export(body["selection"], scope=scope, selected_refs=body.get("refs"))
        document = canonical_json({"kind": kind, "query_scope": query_scope,
                                   "snapshot_ref": snapshot_ref, "arguments": arguments})
        ref, expires_at = retain_context(EXPORT_SCOPE, document)
    return query_success({"export_ref": ref, "expires_at": expires_at, "selection": body["selection"],
                          "row_count": count, "scope": arguments["scope"], "formats": ["csv", "xlsx"]}, snapshot)


@read_endpoint
def relation_export(kind):
    relation_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"], "export_ref")
    document, _ = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    binding = json.loads(document)
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    reader, service = _reader(), _service(kind)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"])
        rows = service.export_rows(fmt, **binding["arguments"])
    # 读事务已结束：生成 CSV/XLSX 只用已读出的行，不再挡别人提交写入。
    response = file_response(service.write_export(rows, fmt))
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def relation_template(kind):
    relation_kind(kind)
    return file_response(WorkbenchRelationFileService.template(kind, download_args({"format"})))


def register_relation_file_routes(bp):
    bp.add_url_rule(BASE + "/<kind>/preview", view_func=relation_import_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/confirm", view_func=relation_import_confirm, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export-preview", view_func=relation_export_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export", view_func=relation_export, methods=["GET"])
    bp.add_url_rule(BASE + "/<kind>/template", view_func=relation_template, methods=["GET"])
