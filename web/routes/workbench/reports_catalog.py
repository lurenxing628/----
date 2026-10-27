"""Four catalog downloads with explicit semantics and snapshot validation."""

from __future__ import annotations

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import ReportPage
from core.models.workbench_report_catalog import ReportCatalogScope
from core.services.report.exporters.xlsx import export_execution_review_xlsx
from core.services.workbench import messages
from core.services.workbench.report.catalog import catalog_facts, catalog_workspace, export_catalog_xlsx
from core.services.workbench.report.exports import ensure_export_size, export_table, metadata
from core.services.workbench.report.facts import WorkbenchReportFacts
from core.services.workbench.report.queries import report_workspace
from core.services.workbench.report.review_projection import project_export_rows
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, page_integer, read_snapshot_time
from .reports import arguments, download_response


def _official(export):
    scope, topic, page, token = arguments(export)
    if topic != "delivery":
        raise WorkbenchCommandRejected("invalid_input", "正式执行复盘只能按工序完成专题看，报表没有变化。请选择工序完成专题后重试。", 400)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    as_of, binding = read_snapshot_time(token)
    # 与现场分析是同一份“整份正式计划 + 台账”重建，和看板、现场页一起排读额度。
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            facts = reader.read(scope)
            snapshot = bind_read_snapshot(facts["scope"].scope(), facts["fingerprint"], token, as_of=as_of, binding=binding)
            data, ordered, labels = report_workspace(facts, snapshot, topic, page)
    if not export:
        return query_success(data, snapshot)
    if request.args.get("format", "xlsx") != "xlsx":
        raise WorkbenchCommandRejected("invalid_input", "正式执行复盘只提供 XLSX，没有开始下载。需要 CSV 请用五个专题的范围导出。", 400)
    selected = project_export_rows(ordered, labels)
    if not selected:
        raise WorkbenchCommandRejected("empty_export", "当前范围里没有可导出的正式工序，没有开始下载。请放宽筛选范围后重新点「导出 XLSX」。", 422)
    decision = ensure_export_size(reader.engine, len(selected))
    # 读事务和读额度都已释放：XLSX 只用已读出的结果生成，不再占着读锁。
    file = reader.engine._build_xlsx_export(filename="正式执行复盘.xlsx", decision=decision,
        build_direct=lambda: export_execution_review_xlsx(selected, summary_rows=metadata(data, snapshot)),
        build_stream=lambda: export_execution_review_xlsx(selected, summary_rows=metadata(data, snapshot), write_only=True))
    return download_response(file, snapshot)


def _catalog_page(kind):
    return ReportPage(page_integer(request.args.get("page", "1")), page_integer(request.args.get("size", "20")),
        request.args.get("sort", "batch_label" if kind == "overdue" else "resource_label"), request.args.get("direction", "asc"))


def _catalog(kind, export=False):
    if kind == "official-review":
        return _official(export)
    allowed = {"source", "plan_ref", "window_date_from", "window_date_to", "query", "page", "size", "sort", "direction", "snapshot_ref"}
    if export:
        allowed.add("format")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "这张报表不支持这些筛选条件，当前筛选没有变化；系统没有把计划完工日期当成统计范围。请刷新页面后重新选择。", 400)
    scope = ReportCatalogScope(kind, **{key: request.args[key] for key in ("source", "plan_ref", "window_date_from", "window_date_to", "query") if key in request.args})
    page = _catalog_page(kind)
    token = request.args.get("snapshot_ref")
    if export and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            facts = catalog_facts(reader, scope)
            snapshot = bind_read_snapshot(facts["scope"].scope(), facts["fingerprint"], token, as_of=as_of, binding=binding)
            data, ordered, selected = catalog_workspace(facts, page, as_of=as_of)
            if not export:
                data["exports"] = {"url": "/api/workbench/v1/reports/" + kind + "/export", "formats": ["csv", "xlsx"], "scope": "all_filtered_rows"}
    if export:
        # 读事务和读额度都已释放：文件只用已读出的结果生成。
        format_name = request.args.get("format", "xlsx")
        file = export_catalog_xlsx(reader, data, selected, snapshot) if format_name == "xlsx" else export_table(reader.engine, data, ordered, snapshot, format_name)
        return download_response(file, snapshot)
    return query_success(data, snapshot)


@api_endpoint
def report_catalog(kind):
    return _catalog(kind)


@api_endpoint
def report_catalog_export(kind):
    return _catalog(kind, True)


def register_report_catalog_routes(bp):
    bp.add_url_rule("/api/workbench/v1/reports/<kind>", view_func=report_catalog, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/reports/<kind>/export", view_func=report_catalog_export, methods=["GET"])
