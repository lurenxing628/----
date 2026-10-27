"""Registration is owned by the main integrator; all report routes are GET-only."""

from __future__ import annotations

from dataclasses import fields

from flask import current_app, g, request, send_file

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import ReportPage, ReportScope, reference
from core.services.workbench import messages
from core.services.workbench.report.columns import public_columns
from core.services.workbench.report.exports import export_table
from core.services.workbench.report.facts import WorkbenchReportFacts
from core.services.workbench.report.queries import SORTS, report_detail, report_workspace
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, page_integer, read_snapshot_time


def _report_page(topic):
    sort = request.args["sort"] if "sort" in request.args else SORTS[topic][0]
    return ReportPage(page_integer(request.args.get("page", "1")), page_integer(request.args.get("size", "20")),
                      sort, request.args.get("direction", "asc"))


def arguments(export=False, detail=False):
    scope_keys = {field.name for field in fields(ReportScope)}
    allowed = scope_keys | {"topic", "page", "size", "sort", "direction", "snapshot_ref"}
    if export:
        allowed.add("format")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "报表的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
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
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    response.headers["X-Workbench-Row-Count"] = str(file.estimated_rows)
    return response


def _read(export=False, operation_ref=None):
    scope, topic, page, token = arguments(export, operation_ref is not None)
    if operation_ref is not None:
        reference(operation_ref)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    as_of, binding = read_snapshot_time(token)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            facts = reader.read(scope)
            snapshot = bind_read_snapshot(facts["scope"].scope(), facts["fingerprint"], token, as_of=as_of, binding=binding)
            if operation_ref is not None:
                data = report_detail(facts, snapshot, operation_ref)
            else:
                data, rows, _ = report_workspace(facts, snapshot, topic, page)
                data["columns"] = public_columns(topic)
                if not export:
                    data["exports"] = {"url": "/api/workbench/v1/analytics/export", "formats": ["csv", "xlsx"], "scope": "all_filtered_rows"}
    if export:
        # 读事务和读额度都已释放：文件只用已读出的结果生成，编码再久也不挡别人提交写入。
        return download_response(export_table(reader.engine, data, rows, snapshot, request.args.get("format", "csv")), snapshot)
    response = query_success(data, snapshot, byte_limit=8 * 1024 * 1024,
        too_large_message="这次要读的报表数据太多，系统没有给出不完整结果。请缩小筛选范围后点「刷新」。")
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def analytics():
    return _read()


@api_endpoint
def analytics_export():
    return _read(export=True)


@api_endpoint
def analytics_operation(operation_ref):
    return _read(operation_ref=operation_ref)


def register_report_routes(bp):
    from .reports_catalog import register_report_catalog_routes

    bp.add_url_rule("/api/workbench/v1/analytics", view_func=analytics, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/analytics/export", view_func=analytics_export, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/analytics/operations/<operation_ref>", view_func=analytics_operation, methods=["GET"])
    register_report_catalog_routes(bp)
