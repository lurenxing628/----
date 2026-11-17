"""Registration is owned by the main integrator; all report routes are GET-only."""

from __future__ import annotations

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_load_limits import MAX_WINDOW_RESPONSE_BYTES
from core.models.workbench_report import reference
from core.services.workbench.report.columns import public_columns
from core.services.workbench.report.exports import export_table
from core.services.workbench.report.facts import WorkbenchReportFacts
from core.services.workbench.report.queries import report_detail, report_workspace
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, read_snapshot_time
from .report_request import arguments, download_response
from .reports_catalog import register_report_catalog_routes


def _read(export=False, operation_ref=None):
    scope, topic, page, token = arguments(export, operation_ref is not None)
    if operation_ref is not None:
        reference(operation_ref)
    format_name = request.args.get("format", "csv") if export else None
    if export and format_name not in ("csv", "xlsx"):
        raise WorkbenchCommandRejected("invalid_input", "只能导出 CSV 或 XLSX，没有开始下载。请重新选择格式。", 400)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    as_of, binding = read_snapshot_time(token)
    bound = {}
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot() as plan_context:
            facts = reader.read(
                plan_context,
                scope,
                bind_snapshot=lambda resolved_scope, fingerprint: bound.setdefault(
                    "snapshot",
                    bind_read_snapshot(resolved_scope, fingerprint, token, as_of=as_of, binding=binding),
                ),
                include_choices=not export and operation_ref is None,
                include_history=export and topic == "records",
                operation_ref=operation_ref,
            )
            snapshot = bound["snapshot"]
            if operation_ref is not None:
                data = report_detail(facts, snapshot, operation_ref)
            else:
                data, rows, _ = report_workspace(
                    facts, snapshot, topic, page, mode=format_name or "workspace"
                )
                data["columns"] = public_columns(topic)
                if not export:
                    data["exports"] = {"url": "/api/workbench/v1/analytics/export", "formats": ["csv", "xlsx"], "scope": "all_filtered_rows"}
    if export:
        # 读事务和读额度都已释放：文件只用已读出的结果生成，编码再久也不挡别人提交写入。
        return download_response(export_table(reader.engine, data, rows, snapshot, format_name), snapshot)
    return query_success(data, snapshot, byte_limit=MAX_WINDOW_RESPONSE_BYTES,
        too_large_message="这次要读的报表数据太多，系统没有给出不完整结果。请缩小筛选范围后点「刷新」。")


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
    bp.add_url_rule("/api/workbench/v1/analytics", view_func=analytics, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/analytics/export", view_func=analytics_export, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/analytics/operations/<operation_ref>", view_func=analytics_operation, methods=["GET"])
    register_report_catalog_routes(bp)
