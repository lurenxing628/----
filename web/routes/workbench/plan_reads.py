"""Read API registration only. The workbench owner registers these routes.

GET /plans?collection=history|scenario&size=20[&cursor=opaque]
GET /plans/<plan_ref> is an alias of the workspace read, sharing its exact scope.
GET /plans/<plan_ref>/workspace[?range_start=local&range_end=local&snapshot_ref=opaque]
GET /plans/<plan_ref>/export?format=csv|xlsx&snapshot_ref=opaque[&range_start=local&range_end=local]
The scope is exact; unknown parameters (including unsupported filters) are refused.
"""

from __future__ import annotations

import json
import re
from io import BytesIO

from flask import current_app, g, request, send_file

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_plan_scope import (
    MAX_PLAN_RESPONSE_BYTES,
    PLAN_READ_TTL_SECONDS,
    PlanCatalogScope,
    PlanReadScope,
)
from core.services.workbench.plan_export import write_plan_export
from core.services.workbench.plan_queries import WorkbenchPlanQueryService
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot

_CURSOR_SCOPE = "workbench-plan-catalog-cursor-v1"


def _arguments(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "计划的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)


def _response(data, snapshot):
    response = query_success(data, snapshot)
    if len(response.get_data()) > MAX_PLAN_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "这次要读的计划数据太多，系统没有给出不完整结果。请缩小日期范围后点「刷新」。", 413)
    response.headers["Cache-Control"] = "no-store"
    return response


def _cursor(scope):
    token = request.args.get("cursor")
    snapshot = request.args.get("snapshot_ref")
    if token is None:
        return None, snapshot
    try:
        payload = json.loads(resolve_public_token(_CURSOR_SCOPE, token, message="翻页位置已失效，请回到第 1 页重新查询。", field="cursor"))
        if not isinstance(payload, dict) or set(payload) != {"scope", "seek", "snapshot_ref"}:
            raise ValueError("Invalid stored cursor")
        if payload["scope"] != scope.scope() or not isinstance(payload["snapshot_ref"], str):
            raise ValueError("Cursor scope mismatch")
        if snapshot is not None and snapshot != payload["snapshot_ref"]:
            raise ValueError("Cursor snapshot mismatch")
        seek = payload["seek"]
        if scope.collection == "history":
            if type(seek) is not int or not 1 <= seek <= (1 << 63) - 1:
                raise ValueError("Invalid history seek")
        elif type(seek) is not str or not seek or "\x00" in seek:
            raise ValueError("Invalid scenario seek")
        return seek, payload["snapshot_ref"]
    except (ValidationError, ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。") from exc


@api_endpoint
def plan_list():
    _arguments(("collection", "size", "cursor", "snapshot_ref"))
    size = request.args.get("size", "20")
    if re.fullmatch(r"[1-9][0-9]?", size) is None:
        raise WorkbenchCommandRejected("invalid_input", "每页数量要填 1 至 50 的整数，列表没有变化。请回到第 1 页重新查询。", 400)
    scope = PlanCatalogScope(request.args.get("collection", "history"), int(size))
    seek, token = _cursor(scope)
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as revision:
        snapshot = bind_read_snapshot(scope.scope(), input_fingerprint({"plan_revision": revision}), token)
        data, next_seek = reader.catalog_page(scope, seek)
        data["page"]["next_cursor"] = None
        if next_seek is not None:
            binding = {"scope": scope.scope(), "snapshot_ref": snapshot["snapshot_ref"], "seek": next_seek}
            data["page"]["next_cursor"] = issue_public_token(_CURSOR_SCOPE, canonical_json(binding), ttl_seconds=PLAN_READ_TTL_SECONDS)
    return _response(data, snapshot)


@api_endpoint
def plan_workspace(plan_ref):
    _arguments(("range_start", "range_end", "snapshot_ref"))
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with reader.read_snapshot():
        data, state = reader.workspace(scope)
        snapshot = bind_read_snapshot(scope.scope(), state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


@api_endpoint
def plan_export(plan_ref):
    _arguments(("format", "range_start", "range_end", "snapshot_ref"))
    fmt, token = request.args.get("format"), request.args.get("snapshot_ref")
    if fmt not in ("csv", "xlsx") or not token:
        raise WorkbenchCommandRejected("invalid_input", "没有选好导出格式，或数据已更新，没有开始下载。请点「刷新」后重新点「导出计划」。", 400)
    scope = PlanReadScope(plan_ref, request.args.get("range_start"), request.args.get("range_end"))
    reader = WorkbenchPlanQueryService(g.db, current_app.logger)
    with reader.read_snapshot():
        data, state = reader.workspace(scope)
        snapshot = bind_read_snapshot(scope.scope(), state, token)
        # Downloads obey the same aggregate HTTP envelope budget as workspace.
        _response(data, snapshot)
        download = write_plan_export(data, snapshot, fmt)
    response = send_file(BytesIO(download.content), mimetype=download.mime_type, as_attachment=True,
                         download_name=download.filename, max_age=0)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Workbench-Row-Count"] = str(download.row_count)
    response.headers["X-Workbench-Snapshot-Ref"] = snapshot["snapshot_ref"]
    response.headers["X-Workbench-Plan-Ref"] = scope.plan_ref
    return response


def register_plan_read_routes(bp):
    bp.add_url_rule("/api/workbench/v1/plans", view_func=plan_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>", endpoint="plan_detail", view_func=plan_workspace, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/workspace", view_func=plan_workspace, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/plans/<plan_ref>/export", view_func=plan_export, methods=["GET"])
