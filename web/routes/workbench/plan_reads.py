"""Read API registration only. The workbench owner registers these routes.

GET /plans?collection=history&size=20[&cursor=opaque]
GET /plans/<plan_ref> is an alias of the workspace read, sharing its exact scope.
GET /plans/<plan_ref>/workspace[?range_start=local&range_end=local&snapshot_ref=opaque]
GET /plans/<plan_ref>/tasks?snapshot_ref=opaque[&range_start=local&range_end=local&page=1&size=5000]
GET /plans/<plan_ref>/gantt-graph?snapshot_ref=opaque[&range_start=local&range_end=local]
GET /plans/<plan_ref>/capacity?snapshot_ref=opaque[&range_start=local&range_end=local]
GET /plans/<plan_ref>/baseline?snapshot_ref=opaque[&range_start=local&range_end=local&page=1&size=5000]
GET /plans/<plan_ref>/export?format=csv|xlsx&snapshot_ref=opaque[&range_start=local&range_end=local]
The scope is exact; unknown parameters (including unsupported filters) are refused.
"""

from __future__ import annotations

import re
from io import BytesIO

from flask import current_app, g, request, send_file

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_scope import (
    MAX_PLAN_RESPONSE_BYTES,
    PLAN_READ_TTL_SECONDS,
    PlanCatalogScope,
    PlanReadScope,
)
from core.services.workbench.plan.export import write_plan_export
from core.services.workbench.plan.queries import WorkbenchPlanQueryService
from web.api_responses import query_success
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot

_CURSOR_SCOPE = "workbench-plan-catalog-cursor-v1"


def _arguments(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "计划的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)


def _response(data, snapshot):
    return query_success(data, snapshot, byte_limit=MAX_PLAN_RESPONSE_BYTES,
        too_large_message="这次要读的计划数据太多，系统没有给出不完整结果。请缩小日期范围后点「刷新」。")


def _cursor(scope_dict):
    token = request.args.get("cursor")
    snapshot = request.args.get("snapshot_ref")
    if token is None:
        return None, snapshot
    try:
        payload = resolve_public_token(_CURSOR_SCOPE, token, message="翻页位置已失效，请回到第 1 页重新查询。", field="cursor")
    except ValidationError as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。") from exc
    seek = payload["seek"]
    valid_seek = type(seek) is int and 1 <= seek <= (1 << 63) - 1
    if payload["scope"] != scope_dict or (snapshot is not None and snapshot != payload["snapshot_ref"]) or not valid_seek:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
    return seek, payload["snapshot_ref"]


@api_endpoint
def plan_list():
    _arguments(("collection", "size", "cursor", "snapshot_ref"))
    size = request.args.get("size", "20")
    if re.fullmatch(r"[1-9][0-9]?", size) is None:
        raise WorkbenchCommandRejected("invalid_input", "每页数量要填 1 至 50 的整数，列表没有变化。请回到第 1 页重新查询。", 400)
    scope = PlanCatalogScope(request.args.get("collection", "history"), int(size))
    scope_dict = scope.scope()
    seek, token = _cursor(scope_dict)
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as revision:
        snapshot = bind_read_snapshot(scope_dict, revision, token)
        data, next_seek = reader.catalog_page(scope, seek)
        data["page"]["next_cursor"] = None
        if next_seek is not None:
            binding = {"scope": scope_dict, "snapshot_ref": snapshot["snapshot_ref"], "seek": next_seek}
            data["page"]["next_cursor"] = issue_public_token(_CURSOR_SCOPE, binding, key=(snapshot["snapshot_ref"], next_seek), ttl_seconds=PLAN_READ_TTL_SECONDS)
    return _response(data, snapshot)


@api_endpoint
def plan_workspace(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref"))
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, state = reader.workspace(scope)
    snapshot = bind_read_snapshot(data["scope"], state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


@api_endpoint
def plan_baseline(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref", "page", "size"))
    token = request.args.get("snapshot_ref")
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "缺少当前计划的数据版本编号，请刷新页面后重试。", 400)
    page_raw, size_raw = request.args.get("page", "1"), request.args.get("size", "5000")
    if re.fullmatch(r"[1-9][0-9]{0,5}", page_raw) is None or re.fullmatch(r"[1-9][0-9]{0,3}", size_raw) is None:
        raise WorkbenchCommandRejected("invalid_input", "原安排对比的分页参数不正确，请刷新页面后重试。", 400)
    page, size = int(page_raw), int(size_raw)
    if size > 5000:
        raise WorkbenchCommandRejected("invalid_input", "原安排对比每页最多读取 5000 条，请缩小每页数量后重试。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, scope_dict, state = reader.baseline_comparison(scope, page=page, size=size)
    snapshot = bind_read_snapshot(scope_dict, state, token)
    return _response(data, snapshot)


@api_endpoint
def plan_tasks(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref", "page", "size"))
    token = request.args.get("snapshot_ref")
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "缺少当前计划的数据版本编号，请刷新页面后重试。", 400)
    page_raw, size_raw = request.args.get("page", "1"), request.args.get("size", "5000")
    if re.fullmatch(r"[1-9][0-9]{0,5}", page_raw) is None or re.fullmatch(r"[1-9][0-9]{0,3}", size_raw) is None:
        raise WorkbenchCommandRejected("invalid_input", "工序安排的分页参数不正确，请刷新页面后重试。", 400)
    page, size = int(page_raw), int(size_raw)
    if size > 5000:
        raise WorkbenchCommandRejected("invalid_input", "工序安排每页最多读取 5000 条，请缩小每页数量后重试。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, scope_dict, state = reader.tasks_page(scope, page=page, size=size)
    snapshot = bind_read_snapshot(scope_dict, state, token)
    return _response(data, snapshot)


@api_endpoint
def plan_gantt_graph(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref"))
    token = request.args.get("snapshot_ref")
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "缺少当前计划的数据版本编号，请刷新页面后重试。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, scope_dict, state = reader.gantt_graph(scope)
    snapshot = bind_read_snapshot(scope_dict, state, token)
    return _response(data, snapshot)


@api_endpoint
def plan_capacity(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref"))
    token = request.args.get("snapshot_ref")
    if not token:
        raise WorkbenchCommandRejected("invalid_input", "缺少当前计划的数据版本编号，请刷新页面后重试。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, scope_dict, state = reader.capacity_projections(scope)
    snapshot = bind_read_snapshot(scope_dict, state, token)
    return _response(data, snapshot)


@api_endpoint
def plan_export(plan_ref):
    _arguments(("format", "range_start", "range_end", "snapshot_ref"))
    fmt, token = request.args.get("format"), request.args.get("snapshot_ref")
    if fmt not in ("csv", "xlsx") or not token:
        raise WorkbenchCommandRejected("invalid_input", "没有选好导出格式，或数据已更新，没有开始下载。请点「刷新」后重新点「导出计划」。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with PLAN_READ_SLOTS.slot():
        with reader.read_snapshot():
            data, state = reader.workspace(scope, include_all_tasks=True)
    snapshot = bind_read_snapshot(data["scope"], state, token)
    # 读事务和读额度都已释放：大小检查和生成文件只用已读出的计划，不再占着读锁。
    download = write_plan_export(data, snapshot, fmt)
    if len(download.content) > MAX_PLAN_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "导出文件超过 8 MB，请缩小范围后重新导出。", 413)
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Plan-Ref"] = scope.plan_ref
    return response


def register_plan_read_routes(bp):
    bp.add_url_rule("/api/workbench/v1/plans", view_func=plan_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>", endpoint="plan_detail", view_func=plan_workspace, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/workspace", view_func=plan_workspace, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/tasks", view_func=plan_tasks, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/gantt-graph", view_func=plan_gantt_graph, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/capacity", view_func=plan_capacity, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/baseline", view_func=plan_baseline, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/export", view_func=plan_export, methods=["GET"])
