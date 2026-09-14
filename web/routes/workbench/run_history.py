"""Explicit GET registration only; sharing the admission URL never enables writes."""

import re

from flask import g, request

from core.models.workbench_run_history import RunHistoryScope, reject
from core.services.workbench.run_history import WorkbenchRunHistoryQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


def _integer(name: str, default: str) -> int:
    value = request.args.get(name, default)
    if re.fullmatch(r"[1-9][0-9]{0,6}", value) is None:
        reject("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。")
    return int(value)


@api_endpoint
def run_history_list():
    allowed = ("page", "size", "state", "accepted_from", "accepted_to", "sort", "order", "snapshot_ref")
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("invalid_input", "排产记录的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    scope = RunHistoryScope(state=request.args.get("state", "all"), accepted_from=request.args.get("accepted_from"),
        accepted_to=request.args.get("accepted_to"), sort=request.args.get("sort", "accepted_at"),
        order=request.args.get("order", "desc"), page=_integer("page", "1"), size=_integer("size", "20"))
    data, fingerprint = WorkbenchRunHistoryQueryService(g.db).catalog(scope)
    snapshot = bind_read_snapshot(scope.scope(), fingerprint, request.args.get("snapshot_ref"))
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_run_history_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/runs", view_func=run_history_list, methods=["GET"])
