"""Download exactly the preflighted process scope, format and read snapshot."""

from flask import current_app, g, request

from core.models.content import content_text
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_actions import process_part_refs
from core.models.workbench_process_file import check_format, file_columns, public_columns
from core.models.workbench_process_table_query import ProcessTablePageRequest, wire_process_scope
from core.services.workbench.process import scope as process_scope
from core.services.workbench.process.file_codec import encode_process_file
from core.services.workbench.process.file_export import (
    count_process_export_rows,
    process_export_rows,
    select_export_parts,
)
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from web.api_responses import query_success

from .material_actions_context import opaque_ref
from .process_action_context import EXPORT_SCOPE
from .process_collections import collection_scope
from .process_json import read_process_json
from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    admit_export_selection,
    download_query,
    file_response,
    read_endpoint,
    resolve_context,
    retain_context,
)


def _query_scope(body):
    page_request, query_scope = collection_scope(body["scope"], body["page_size"])
    if "target_ref" in body:
        if type(body["target_ref"]) is not str:
            raise WorkbenchCommandRejected("invalid_input", "当前零件编号不对，没有开始下载。请刷新详情后重新点「导出」。", 400)
        if body["scope"]:
            raise WorkbenchCommandRejected("invalid_input", "当前详情导出不需要其他筛选条件，没有开始下载。请直接点「导出」。", 400)
        process_scope.check_part_ref(body["target_ref"])
        query_scope = {"kind": "part", "entity_ref": body["target_ref"]}
    return page_request, query_scope


def _export_selection(body, page_request):
    """The preflight's admitted refs (None unless explicit) and its effective list request."""
    selection = admit_export_selection(
        body,
        explicit_value="explicit",
        message="请选择全部、全部筛选结果，或者勾选具体记录；只有勾选方式才认记录编号。",
    )
    refs, target_ref = body.get("refs"), body.get("target_ref")
    if target_ref is not None and (selection != "explicit" or refs != [target_ref]):
        raise WorkbenchCommandRejected("invalid_input", "详情只能导出当前零件，不能切换为其他范围。", 400)
    if selection == "explicit":
        return [target_ref] if target_ref is not None else process_part_refs(refs, allow_empty=True), page_request
    return None, ProcessTablePageRequest() if selection == "all" else page_request


@read_endpoint
def process_file_export_preview(kind):
    file_columns(kind)
    body = read_process_json("工艺文件导出", 16 * 1024 * 1024)
    required = {"format", "selection", "scope", "snapshot_ref", "page_size"}
    if not required <= set(body) or set(body) - required - {"refs", "target_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "导出范围不完整或有多余项，没有开始下载。请刷新页面后重新点「导出」。", 400)
    check_format(body["format"])
    token = opaque_ref(body["snapshot_ref"])
    page_request, query_scope = _query_scope(body)
    target_ref = body.get("target_ref")
    reader = WorkbenchProcessQueryService(g.db, current_app.logger, part_ref=target_ref)
    with reader.read_snapshot() as fact_scope:
        read_binding = resolve_read_snapshot(token)
        snapshot = bind_read_snapshot(query_scope, fact_scope.state_fingerprint(), token, binding=read_binding)
        refs, effective = _export_selection(body, page_request)
        parts = select_export_parts(fact_scope, refs, effective)
        facts = fact_scope.raw_facts()
    # 读事务已结束：逐格试算导出只用读快照里的工艺资料。
    count = count_process_export_rows(kind, parts, facts, body["format"])
    scope = {} if target_ref is not None else wire_process_scope(effective)
    document = {"kind": kind, "query_scope": query_scope, "snapshot_ref": token, "format": body["format"],
                "target_ref": target_ref, "refs": refs, "request": effective}
    ref, expiry = retain_context(EXPORT_SCOPE, document, read_binding,
                                 key=(kind, read_binding.scope, token, content_text(body)))
    return query_success({"kind": kind, "export_ref": ref, "expires_at": expiry, "selection": body["selection"],
                          "scope": scope, "target_ref": target_ref, "row_count": count,
                          "part_count": len(parts), "format": body["format"], "columns": public_columns(kind)}, snapshot)


@read_endpoint
def process_file_export(kind):
    file_columns(kind)
    download_query({"export_ref"})
    saved, read_binding = resolve_context(EXPORT_SCOPE, opaque_ref(request.args["export_ref"]), "snapshot_stale")
    if saved["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "预检结果属于另一类工艺文件，没有开始下载；系统没有替你换内容。请点「重新预检」。")
    reader = WorkbenchProcessQueryService(g.db, current_app.logger, part_ref=saved["target_ref"])
    with reader.read_snapshot() as fact_scope:
        snapshot = bind_read_snapshot(
            saved["query_scope"],
            fact_scope.state_fingerprint(),
            saved["snapshot_ref"],
            binding=read_binding,
        )
        parts = select_export_parts(fact_scope, saved["refs"], saved["request"])
        facts = fact_scope.raw_facts()
    # 读事务已结束：文件只用读快照里的工艺资料生成，编码再久也不挡别人提交写入。
    download = encode_process_file(kind, process_export_rows(kind, parts, facts), saved["format"])
    response = file_response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def process_file_template(kind):
    file_columns(kind)
    download_query({"format"})
    check_format(request.args["format"])
    return file_response(encode_process_file(kind, [], request.args["format"], template=True))
