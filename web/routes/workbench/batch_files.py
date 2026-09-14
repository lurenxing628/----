"""Batch first-sheet files, using common contexts and the existing command bus."""

import json
from io import BytesIO

from flask import current_app, g, jsonify, request, send_file

from core.models.workbench_batch import object_fields, public_ref
from core.models.workbench_batch_file import MAX_BYTES, MAX_ROWS, MIME
from core.models.workbench_batch_query import batch_scope, snapshot_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_file_codec import TEMPLATE, write_batch_file
from core.services.workbench.batch_files import WorkbenchBatchFileService
from core.services.workbench.batch_queries import WorkbenchBatchQueryService
from core.services.workbench.commands import WorkbenchCommandService

from .api_responses import api_endpoint, query_success
from .batch_context import command_body, json_body, load_preview, save_preview
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def download(content, name, count):
    response = send_file(BytesIO(content), mimetype=MIME, as_attachment=True, download_name=name)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(count)
    return response


@api_endpoint
def batch_template():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "模板下载不需要其他条件，没有开始下载。请直接点「下载批次模板」。", 400)
    return download(write_batch_file(TEMPLATE["sample_rows"], template=True), "批次导入模板.xlsx", len(TEMPLATE["sample_rows"]))


@api_endpoint
def batch_import_preview():
    if request.args or set(request.files) != {"file"} or len(request.files.getlist("file")) != 1:
        raise WorkbenchCommandRejected("invalid_input", "请先选择一个批次 XLSX 文件，再点「导入预检」。", 400)
    if set(request.form) != {"mode", "scope", "snapshot_ref"} or any(len(request.form.getlist(key)) != 1 for key in request.form):
        raise WorkbenchCommandRejected("invalid_input", "没有选好导入方式，或本页数据已过期，文件还没有导入。请刷新页面后重新选择文件。", 400)
    try:
        scope = batch_scope(json.loads(request.form["scope"]))
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "文件导入范围不对，文件还没有导入。请刷新页面后重新点「导入预检」。", 400) from exc
    upload = request.files["file"]
    if not upload.filename or not upload.filename.lower().endswith(".xlsx") or not request.form["snapshot_ref"]:
        raise WorkbenchCommandRejected("invalid_input", "批次文件必须是 XLSX，并且要在当前页面数据下导入；文件还没有导入。请刷新页面后重新选择文件。", 400)
    content = upload.stream.read(MAX_BYTES + 1)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        bind_read_snapshot(snapshot_scope(scope), fingerprint, request.form["snapshot_ref"])
        document = WorkbenchBatchFileService(g.db, current_app.logger).preview(content, request.form["mode"])
        token = save_preview("import_confirm", None, document, fingerprint)
        data = {**document, "preview_ref": token, "write_context": None}
        if document["can_confirm"]:
            data["write_context"] = issue_write_context(token, ["batch.import_confirm"], {"fingerprint": fingerprint, "input": document})
        snapshot = bind_read_snapshot({"kind": "batch_import_preview", "preview_ref": token}, fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_import_confirm():
    body = command_body()
    normalized = dict(object_fields(body["input"], ("preview_ref",), ("preview_ref",)))
    token = normalized["preview_ref"]
    if not isinstance(token, str) or not token:
        raise WorkbenchCommandRejected("invalid_input", "预检结果编号缺失，文件还没有导入。请重新点「导入预检」。", 400)

    def guard():
        binding = load_preview(token, "import_confirm", None)
        fingerprint = WorkbenchBatchQueryService(g.db, current_app.logger).fingerprint()
        if binding["fingerprint"] != fingerprint:
            raise WorkbenchCommandRejected("stale_write", "预检之后批次资料有变化，文件还没有导入。请重新点「导入预检」。")
        validate_write_context(body["write_token"], token, "batch.import_confirm", {"fingerprint": fingerprint, "input": binding["input"]})
        return binding["input"]

    return jsonify(WorkbenchCommandService(g.db, current_app.logger).execute(request_key=body["request_key"], action="batch.import_confirm",
        context_ref=token, normalized_input=normalized, guard=guard, mutate=lambda document: WorkbenchBatchFileService(g.db, current_app.logger).apply(document)))


@api_endpoint
def batch_export_preview():
    body = object_fields(json_body(), ("selection", "scope", "refs"), ("selection", "scope"))
    scope = batch_scope(body["scope"])
    if body["selection"] not in ("selected", "filtered") or not scope.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "请先选好导出当前筛选还是导出选中的批次，没有开始下载。数据已更新时请先点「刷新」，再点「下载批次清单」。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        bind_read_snapshot(snapshot_scope(scope), fingerprint, scope["snapshot_ref"])
        if body["selection"] == "selected":
            refs = body.get("refs")
            if not isinstance(refs, list) or not 1 <= len(refs) <= MAX_ROWS:
                raise WorkbenchCommandRejected("invalid_input", "导出要选 1 至 5000 批批次且不能重复，没有开始下载。请重新选择后点「下载批次清单」。", 400)
            refs = [public_ref(ref) for ref in refs]
            if len(set(refs)) != len(refs):
                raise WorkbenchCommandRejected("invalid_input", "选中的批次有重复，没有开始下载。请重新选择后点「下载批次清单」。", 400)
            for ref in refs:
                reader.resolve(public_ref(ref))
        else:
            if "refs" in body:
                raise WorkbenchCommandRejected("invalid_input", "导出当前筛选时不能再带选中的批次，没有开始下载。请重新选择后点「下载批次清单」。", 400)
            refs = reader.selection(scope)["refs"]
        token = save_preview("export", None, {"refs": refs}, fingerprint)
        snapshot = bind_read_snapshot({"kind": "batch_export", "export_ref": token}, fingerprint)
    return query_success({"export_ref": token, "count": len(refs), "selection": body["selection"]}, snapshot)


@api_endpoint
def batch_export():
    if set(request.args) != {"export_ref"} or len(request.args.getlist("export_ref")) != 1:
        raise WorkbenchCommandRejected("invalid_input", "导出范围已过期，没有开始下载。请重新点「下载批次清单」。", 400)
    binding = load_preview(request.args["export_ref"], "export", None)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        if binding["fingerprint"] != fingerprint:
            raise WorkbenchCommandRejected("snapshot_stale", "导出范围里的批次有变化，没有开始下载。请重新点「下载批次清单」。")
        entities = [reader.detail(ref) for ref in binding["input"]["refs"]]
        content = WorkbenchBatchFileService.export(entities)
    return download(content, "批次清单.xlsx", len(entities))


def register_batch_file_routes(bp):
    base = "/api/workbench/v1/entities/batch"
    for suffix, function, method in (("template", batch_template, "GET"), ("import-preview", batch_import_preview, "POST"),
                                    ("import-confirm", batch_import_confirm, "POST"), ("export-preview", batch_export_preview, "POST"), ("export", batch_export, "GET")):
        bp.add_url_rule(base + "/" + suffix, view_func=function, methods=[method])
