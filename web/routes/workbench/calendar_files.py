"""全局工作日历的文件路由。

导出范围是日期区间，不是列表筛选：日历页没有列表也没有勾选，三档范围在这里没有意义。
区间的读快照要现算（`range_snapshot`），月视图的快照绑的是一个月，覆盖不了任意区间。
"""


from flask import current_app, g, request

from core.infrastructure.transaction import TransactionManager
from core.models.content import content_text
from core.models.workbench_calendar_file import (
    INSTRUCTIONS,
    TEMPLATE_VERSION,
    calendar_kind,
    public_columns,
)
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_resource_action import resource_refs
from core.models.workbench_table_descriptor import FILE_FORMATS
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.facts.file_writer import check_capacity
from core.services.workbench.facts.source_revisions import (
    CALENDAR_SOURCE_KEYS,
    OPERATOR_CALENDAR_SOURCE_KEYS,
    read_source_revisions,
)
from core.services.workbench.resource.calendar_files.file_writer import write_calendar_file
from core.services.workbench.resource.calendar_files.files import WorkbenchCalendarFileService, check_range
from core.services.workbench.resource.calendar_files.operator_files import (
    KIND as OPERATOR_KIND,
)
from core.services.workbench.resource.calendar_files.operator_files import (
    WorkbenchOperatorCalendarFileService,
)
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot, resolve_read_snapshot
from .resource_action_context import (
    EXPIRED_MESSAGE,
    EXPORT_SCOPE,
    IMPORT_MISMATCH_MESSAGE,
    PREVIEW_SCOPE,
    confirm_body,
    download_args,
    file_response,
    issue_file_preview,
    json_body,
    opaque_ref,
    read_endpoint,
    resolve_context,
    retain_context,
    upload_body,
)
from .write_context import resolve_action_preview

BASE = "/api/workbench/v1/calendar-files"


def _service(kind):
    if kind == OPERATOR_KIND:
        return WorkbenchOperatorCalendarFileService(g.db, current_app.logger)
    return WorkbenchCalendarFileService(g.db, kind, current_app.logger)


def _operator_refs(kind, body):
    """个人日历可以只导某几个人；不给就是全部人员。全局日历没有这一维。"""
    scope = body.get("scope")
    if scope is None:
        return {}
    if kind != OPERATOR_KIND or type(scope) is not dict or set(scope) != {"operator_refs"}:
        raise WorkbenchCommandRejected("invalid_input", "导出范围里有不支持的项，没有开始下载。请刷新页面后重新点「导出」。", 400)
    return {"selected_refs": resource_refs(scope["operator_refs"], allow_empty=True)}


def _range_input(body):
    value = body["range"]
    if type(value) is not dict or set(value) != {"start_date", "end_date"} \
            or any(type(value[key]) is not str for key in value):
        raise WorkbenchCommandRejected("invalid_input", "请选好开始和结束日期，没有开始下载。选好后重新点「导出」。", 400)
    check_range(value["start_date"], value["end_date"])
    return value["start_date"], value["end_date"]


@read_endpoint
def calendar_import_preview(kind):
    calendar_kind(kind)
    content, fmt, mode = upload_body()
    service = _service(kind)
    preview = service.preview_import(content, file_format=fmt, mode=mode)
    data = issue_file_preview(preview, columns=public_columns(kind),
                              instructions=INSTRUCTIONS[kind], template_version=TEMPLATE_VERSION)
    source_keys = OPERATOR_CALENDAR_SOURCE_KEYS if kind == OPERATOR_KIND else CALENDAR_SOURCE_KEYS
    snapshot = bind_read_snapshot({"kind": kind, "operation": kind + ".import",
                                   "preview_ref": data["preview_ref"]}, read_source_revisions(g.db, source_keys))
    return query_success(data, snapshot, preview.as_dict()["notices"])


@api_endpoint
def calendar_import_confirm(kind):
    calendar_kind(kind)
    body = confirm_body()
    ref, operation = body["input"]["preview_ref"], kind + ".import"
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=operation, context_ref=ref, normalized_input={"preview_ref": ref},
        guard=lambda: resolve_action_preview(PREVIEW_SCOPE, ref, operation, body["write_token"],
                                             expired_message=EXPIRED_MESSAGE, mismatch_message=IMPORT_MISMATCH_MESSAGE),
        mutate=lambda preview: _service(kind).confirm_import(preview))
    return json_response(outcome)


def _bind_export_snapshot(kind, query_scope, provided, read_binding):
    source_keys = OPERATOR_CALENDAR_SOURCE_KEYS if kind == OPERATOR_KIND else CALENDAR_SOURCE_KEYS
    return bind_read_snapshot(query_scope, read_source_revisions(g.db, source_keys), provided, binding=read_binding)


@read_endpoint
def calendar_export_preview(kind):
    calendar_kind(kind)
    body = json_body({"range"}, {"snapshot_ref", "scope"})
    start_date, end_date = _range_input(body)
    arguments = {"start_date": start_date, "end_date": end_date, **_operator_refs(kind, body)}
    provided = opaque_ref(body["snapshot_ref"]) if "snapshot_ref" in body else None
    service = _service(kind)
    query_scope = {"kind": kind, **arguments}
    read_binding = resolve_read_snapshot(provided) if provided is not None else None
    with TransactionManager(g.db).transaction():
        if isinstance(service, WorkbenchOperatorCalendarFileService):
            codes = service.export_codes(arguments.get("selected_refs"))
            snapshot = _bind_export_snapshot(kind, query_scope, provided, read_binding)
            count = service.preview_export(start_date=start_date, end_date=end_date, codes=codes)
        else:
            snapshot = _bind_export_snapshot(kind, query_scope, provided, read_binding)
            count = service.preview_export(start_date=start_date, end_date=end_date)
        document = {"query_scope": query_scope, "snapshot_ref": snapshot["snapshot_ref"], "row_count": count}
        ref, expires_at = retain_context(EXPORT_SCOPE, document, read_binding,
                                         key=(kind, document["snapshot_ref"], content_text(arguments)))
    return query_success({"export_ref": ref, "expires_at": expires_at, "range": arguments,
                          "row_count": count, "formats": FILE_FORMATS}, snapshot)


@read_endpoint
def calendar_export(kind):
    calendar_kind(kind)
    fmt = download_args({"export_ref", "format"})
    ref = opaque_ref(request.args["export_ref"])
    binding, read_binding = resolve_context(EXPORT_SCOPE, ref, "snapshot_stale")
    scope = binding["query_scope"]
    if scope["kind"] != kind:
        raise WorkbenchCommandRejected("snapshot_stale", "这次导出的编号属于另一类记录，没有开始下载。请刷新页面后重新点「导出」。")
    service = _service(kind)
    with TransactionManager(g.db).transaction():
        if isinstance(service, WorkbenchOperatorCalendarFileService):
            codes = service.export_codes(scope.get("selected_refs"))
            snapshot = _bind_export_snapshot(kind, scope, binding["snapshot_ref"], read_binding)
            check_capacity(binding["row_count"], fmt)
            rows = service.export_rows(scope["start_date"], scope["end_date"], codes=codes)
        else:
            snapshot = _bind_export_snapshot(kind, scope, binding["snapshot_ref"], read_binding)
            check_capacity(binding["row_count"], fmt)
            rows = service.export_rows(start_date=scope["start_date"], end_date=scope["end_date"])
    download = write_calendar_file(kind, rows, fmt)
    response = file_response(download)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    return response


@read_endpoint
def calendar_template(kind):
    calendar_kind(kind)
    return file_response(write_calendar_file(kind, [], download_args({"format"}), template=True))


def register_calendar_file_routes(bp):
    bp.add_url_rule(BASE + "/<kind>/preview", view_func=calendar_import_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/confirm", view_func=calendar_import_confirm, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export-preview", view_func=calendar_export_preview, methods=["POST"])
    bp.add_url_rule(BASE + "/<kind>/export", view_func=calendar_export, methods=["GET"])
    bp.add_url_rule(BASE + "/<kind>/template", view_func=calendar_template, methods=["GET"])
