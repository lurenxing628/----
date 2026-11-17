"""Report request shapes and downloads shared by the analytics and catalog routes."""

from dataclasses import fields

from flask import request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import ReportPage, ReportScope
from core.services.workbench import messages
from core.services.workbench.report.queries import SORTS

from .read_context import page_integer
from .request_json import single_value_arguments


def _report_page(topic):
    sort = request.args["sort"] if "sort" in request.args else SORTS[topic][0]
    return ReportPage(page_integer(request.args.get("page", "1")), page_integer(request.args.get("size", "20")),
                      sort, request.args.get("direction", "asc"))


def arguments(export=False, detail=False):
    scope_keys = {field.name for field in fields(ReportScope)}
    allowed = scope_keys | {"topic", "page", "size", "sort", "direction", "snapshot_ref"}
    if export:
        allowed.add("format")
    single_value_arguments(allowed, message="报表的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    scope = ReportScope(**{key: request.args[key] for key in scope_keys if key in request.args})
    topic = request.args.get("topic", "delivery")
    if topic not in SORTS:
        raise WorkbenchCommandRejected("invalid_input", "这个报表专题不支持，报表没有变化。请从侧栏进入「报表中心」重新选择。", 400)
    page = _report_page(topic)
    token = request.args.get("snapshot_ref")
    if (export or detail) and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    return scope, topic, page, token


def download_response(file, snapshot):
    response = send_file(file.data, mimetype=file.content_type, as_attachment=True, download_name=file.filename, max_age=0)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    response.headers["X-Workbench-Row-Count"] = str(file.estimated_rows)
    return response
