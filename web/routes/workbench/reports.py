"""Registration is owned by the main integrator; all report routes are GET-only."""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime

from flask import current_app, g, request, send_file

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_report import ReportPage, ReportScope, reference
from core.services.workbench.report_columns import public_columns
from core.services.workbench.report_exports import export_table
from core.services.workbench.report_facts import WorkbenchReportFacts
from core.services.workbench.report_queries import SORTS, report_workspace
from web.public_token_registry import issue_public_token, resolve_public_token

from . import read_context
from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


def report_read_time(token):
    if token is None:
        return read_context.datetime.now().replace(microsecond=0)
    try:
        payload = json.loads(resolve_public_token(read_context._SCOPE, token,
            message="读取范围已失效，请重新刷新。", field="snapshot_ref"))
        as_of = datetime.fromisoformat(payload["as_of"])
        if as_of.tzinfo is not None:
            raise ValueError("factory local time required")
        return as_of
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "读取范围已失效，请重新刷新；未自动切换到新数据。") from exc


def bind_report_snapshot(scope, fingerprint, token, as_of):
    if token is not None:
        return bind_read_snapshot(scope, fingerprint, token)
    captured = as_of.isoformat(timespec="seconds")
    payload = {"version": 2, "source": "production", "scope_hash": input_fingerprint(scope),
               "fingerprint": fingerprint, "as_of": captured}
    reference = issue_public_token(read_context._SCOPE, canonical_json(payload), ttl_seconds=900)
    return {"snapshot_ref": reference, "as_of": captured}


def _report_page(topic):
    try:
        raw_page, raw_size = request.args.get("page", "1"), request.args.get("size", "20")
        if not raw_page.isascii() or not raw_page.isdigit() or not raw_size.isascii() or not raw_size.isdigit():
            raise ValueError("page integer")
        sort = request.args["sort"] if "sort" in request.args else SORTS[topic][0]
        return ReportPage(int(raw_page), int(raw_size), sort, request.args.get("direction", "asc"))
    except ValueError as exc:
        raise WorkbenchCommandRejected("invalid_input", "页码和每页数量必须为整数。", 400) from exc


def arguments(export=False, detail=False):
    scope_keys = {field.name for field in fields(ReportScope)}
    allowed = scope_keys | {"topic", "page", "size", "sort", "direction", "snapshot_ref"}
    if export:
        allowed.add("format")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "报表包含未知或重复参数，未忽略筛选条件。", 400)
    scope = ReportScope(**{key: request.args[key] for key in scope_keys if key in request.args})
    topic = request.args.get("topic", "delivery")
    if topic not in SORTS:
        raise WorkbenchCommandRejected("invalid_input", "未知报表专题。", 400)
    page = _report_page(topic)
    token = request.args.get("snapshot_ref")
    if (export or detail or page.number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_required", "分页、详情或导出必须使用已读取的范围快照。", 400)
    return scope, topic, page, token


def download_response(file, snapshot):
    response = send_file(file.data, mimetype=file.content_type, as_attachment=True, download_name=file.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Snapshot"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-As-Of"] = snapshot["as_of"]
    response.headers["X-Workbench-Row-Count"] = str(file.estimated_rows)
    return response


def _read(export=False, operation_ref=None):
    scope, topic, page, token = arguments(export, operation_ref is not None)
    if operation_ref is not None:
        reference(operation_ref)
    reader = WorkbenchReportFacts(g.db, current_app.logger)
    as_of = report_read_time(token)
    with reader.read_snapshot():
        facts = reader.read(scope, as_of=as_of)
        snapshot = bind_report_snapshot(facts["scope"].scope(), facts["fingerprint"], token, as_of)
        data, rows, _ = report_workspace(reader, facts, snapshot, topic, page, operation_ref)
        data["columns"] = public_columns(topic)
        data["exports"] = {"url": "/api/workbench/v1/analytics/export", "formats": ["csv", "xlsx"], "scope": "all_filtered_rows"}
        if export:
            file = export_table(reader.engine, data, rows, snapshot, request.args.get("format", "csv"))
    if export:
        return download_response(file, snapshot)
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    if len(response.get_data()) > 8 * 1024 * 1024:
        raise WorkbenchCommandRejected("query_too_large", "报表响应超出完整读取上限，未返回截断数据。", 413)
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
