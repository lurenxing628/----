"""全局工作日历的文件路由。

导出范围是日期区间，不是列表筛选：日历页没有列表也没有勾选，三档范围在这里没有意义。
区间的读快照要现算（`range_snapshot`），月视图的快照绑的是一个月，覆盖不了任意区间。
"""

import json

from flask import current_app, g, jsonify, request

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_calendar_file import (
    INSTRUCTIONS,
    TEMPLATE_VERSION,
    calendar_kind,
    public_columns,
)
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendar_files.files import WorkbenchCalendarFileService
from core.services.workbench.resource.calendar_files.operator_files import (
    KIND as OPERATOR_KIND,
)
from core.services.workbench.resource.calendar_files.operator_files import (
    WorkbenchOperatorCalendarFileService,
)
from web.api_responses import query_success

from .api_responses import api_endpoint
from .calendars_preview import calendar_now
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
    upload_body,
)

BASE = "/api/workbench/v1/calendar-files"


def _service(kind):
    if kind == OPERATOR_KIND:
        return WorkbenchOperatorCalendarFileService(g.db, current_app.logger, clock=calendar_now)
    return WorkbenchCalendarFileService(g.db, kind, current_app.logger, clock=calendar_now)


def _operator_refs(kind, body):
    """个人日历可以只导某几个人；不给就是全部人员。全局日历没有这一维。"""
    scope = body.get("scope")
    if scope is None:
        return {}
    if kind != OPERATOR_KIND or type(scope) is not dict or set(scope) != {"operator_refs"}:
        raise WorkbenchCommandRejected("invalid_input", "导出范围里有不支持的项，没有开始下载。请刷新页面后重新点「导出」。", 400)
    return {"selected_refs": scope["operator_refs"]}


def _range_input(body):
    value = body["range"]
    if type(value) is not dict or set(value) != {"start_date", "end_date"} \
            or any(type(value[key]) is not str for key in value):
        raise WorkbenchCommandRejected("invalid_input", "请选好开始和结束日期，没有开始下载。选好后重新点「导出」。", 400)
    return value["start_date"], value["end_date"]


@read_endpoint
def calendar_import_preview(kind):
    calendar_kind(kind)
    content, fmt, mode = upload_body()
    preview = _service(kind).preview_import(content, file_format=fmt, mode=mode)
    data = issue_file_preview(preview, content, columns=public_columns(kind),
                              instructions=INSTRUCTIONS[kind], template_version=TEMPLATE_VERSION)
    # 预检文档本身就是这次读到的全部日历事实，拿它的摘要当读快照指纹。
    snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import",
                                   "preview_ref": data["preview_ref"]}, preview.digest)
    return query_success(data, snapshot, preview.as_dict()["notices"])


def _apply(kind, checked):
    preview, content = checked
    original = preview.as_dict()["request"]
    return _service(kind).confirm_import(preview, content, file_format=original["format"], mode=original["mode"])


@api_endpoint
def calendar_import_confirm(kind):
    calendar_kind(kind)
    body = confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + ".import"
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_import_preview(ref, operation, body["write_token"]),
        mutate=lambda checked: _apply(kind, checked))
    return jsonify(outcome)


@read_endpoint
def calendar_export_preview(kind):
    calendar_kind(kind)
    body = json_body({"range"}, {"snapshot_ref", "scope"})
    start_date, end_date = _range_input(body)
    extra = _operator_refs(kind, body)
    provided = opaque_ref(body["snapshot_ref"], "snapshot_ref") if body.get("snapshot_ref") else None
    service = _service(kind)
    with TransactionManager(g.db).transaction():
        fingerprint = service.range_snapshot(start_date, end_date, **extra)
        query_scope = {"kind": kind, "start_date": start_date, "end_date": end_date, **extra}
        snapshot = bind_read_snapshot(query_scope, fingerprint, provided)
        arguments, count = service.preview_export(start_date=start_date, end_date=end_date, **extra)
        document = canonical_json({"kind": kind, "query_scope": query_scope,
                                   "snapshot_ref": snapshot["snapshot_ref"], "arguments": arguments})
        ref, expires_at = retain_context(EXPORT_SCOPE, document)
    return query_success({"export_ref": ref, "expires_at": expires_at, "range": arguments,
                          "row_count": count, "formats": ["csv", "xlsx"]}, snapshot)


@read_endpoint
def calendar_export(kind):
    calendar_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"], "export_ref")
    document, _ = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    binding = json.loads(document)
    if binding["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    service = _service(kind)
    with TransactionManager(g.db).transaction():
        fingerprint = service.range_snapshot(**binding["arguments"])
        snapshot = bind_read_snapshot(binding["query_scope"], fingerprint, binding["snapshot_ref"])
        download = service.export(fmt, **binding["arguments"])
    response = file_response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def calendar_template(kind):
    calendar_kind(kind)
    return file_response(WorkbenchCalendarFileService.template(kind, download_args({"format"})))


def register_calendar_file_routes(bp):
    bp.add_url_rule(BASE + "/<kind>/preview", view_func=calendar_import_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/confirm", view_func=calendar_import_confirm, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export-preview", view_func=calendar_export_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export", view_func=calendar_export, methods=["GET"])
    bp.add_url_rule(BASE + "/<kind>/template", view_func=calendar_template, methods=["GET"])
