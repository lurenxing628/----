"""Four catalog downloads with explicit semantics and snapshot validation."""

from __future__ import annotations

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_report import ReportPage
from core.models.workbench_report_catalog import ReportCatalogScope
from core.services.report.exporters.xlsx import export_execution_review_xlsx
from core.services.workbench import messages
from core.services.workbench.report_catalog import catalog_facts, catalog_workspace, export_catalog_xlsx
from core.services.workbench.report_exports import ensure_export_size, export_table, metadata
from core.services.workbench.report_facts import WorkbenchReportFacts
from core.services.workbench.report_queries import report_workspace

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .reports import arguments, bind_report_snapshot, download_response, report_read_time


def _official(export):
    scope, topic, page, token = arguments(export)
    if topic != "delivery":
        raise WorkbenchCommandRejected("invalid_input", "正式执行复盘只能按工序完成专题看，报表没有变化。请选择工序完成专题后重试。", 400)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    as_of = report_read_time(token)
    with reader.read_snapshot():
        facts = reader.read(scope, as_of=as_of)
        snapshot = bind_report_snapshot(facts["scope"].scope(), facts["fingerprint"], token, as_of)
        data, ordered, labels = report_workspace(reader, facts, snapshot, topic, page)
        if not export:
            response = query_success(data, snapshot)
            response.headers["Cache-Control"] = "no-store"
            return response
        if request.args.get("format", "xlsx") != "xlsx":
            raise WorkbenchCommandRejected("invalid_input", "正式执行复盘只提供 XLSX，没有开始下载。需要 CSV 请用五个专题的范围导出。", 400)
        selected = [labels[row["operation_ref"]] for row in ordered]
        if not selected:
            raise WorkbenchCommandRejected("empty_export", "当前范围里没有可导出的正式工序，没有开始下载。请放宽筛选范围后重新点「导出 XLSX」。", 422)
        ensure_export_size(reader.engine, len(selected))
        file = reader.engine._build_xlsx_export(report_name="正式执行复盘", filename="正式执行复盘.xlsx",
            estimated_rows=len(selected),
            build_direct=lambda: export_execution_review_xlsx(selected, summary_rows=metadata(data, snapshot)),
            build_stream=lambda: export_execution_review_xlsx(selected, summary_rows=metadata(data, snapshot), write_only=True))
    return download_response(file, snapshot)


def _catalog_page(kind):
    try:
        return ReportPage(int(request.args.get("page", "1")), int(request.args.get("size", "20")),
            request.args.get("sort", "batch_label" if kind == "overdue" else "resource_label"), request.args.get("direction", "asc"))
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。", 400) from exc


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
    if (export or page.number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    with reader.read_snapshot():
        facts = catalog_facts(reader, scope)
        snapshot = bind_read_snapshot(facts["scope"].scope(), facts["fingerprint"], token)
        data, ordered, selected = catalog_workspace(reader, facts, snapshot, page)
        data["exports"] = {"url": "/api/workbench/v1/reports/" + kind + "/export", "formats": ["csv", "xlsx"], "scope": "all_filtered_rows"}
        if export:
            format_name = request.args.get("format", "xlsx")
            file = export_catalog_xlsx(reader, data, selected, snapshot) if format_name == "xlsx" else export_table(reader.engine, data, ordered, snapshot, format_name)
    if export:
        return download_response(file, snapshot)
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def report_catalog(kind):
    return _catalog(kind)


@api_endpoint
def report_catalog_export(kind):
    return _catalog(kind, True)


def register_report_catalog_routes(bp):
    bp.add_url_rule("/api/workbench/v1/reports/<kind>", view_func=report_catalog, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/reports/<kind>/export", view_func=report_catalog_export, methods=["GET"])
