"""Dashboard-only GET adapters; no command, worker or adoption registration."""

from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_dashboard import MAX_BYTES, DashboardAnalysisQuery
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.run.candidate_comparison import read_candidate_comparison
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, page_integer, read_snapshot_time, resolve_read_snapshot


def _response(data, snapshot):
    return query_success(data, snapshot, byte_limit=MAX_BYTES)


def _arguments(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "分析的查询条件有重复或不支持的项，当前范围没有变化。请点「刷新分析」后重试。", 400)


@api_endpoint
def dashboard_analysis():
    _arguments(("plan_ref", "section", "page", "size", "resource_ref", "locate_batch_ref", "snapshot_ref"))
    plan_ref = request.args.get("plan_ref")
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        value = request.args.get(key, default)
        numbers[key] = page_integer(value, message="影响分析的页码或每页数量无效。")
    query = DashboardAnalysisQuery(request.args.get("section", "delivery"), numbers["page"], numbers["size"],
                                   request.args.get("resource_ref"), request.args.get("locate_batch_ref"))
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    with PLAN_READ_SLOTS.slot():
        data, state = read_dashboard_analysis(g.db, plan_ref, query=query, as_of=as_of)
    snapshot = bind_read_snapshot(query.scope(plan_ref), state, token, as_of=data["as_of"], binding=binding)
    return _response(data, snapshot)


@api_endpoint
def dashboard_candidate_comparison(candidate_ref):
    _arguments(("range_start", "range_end", "batch_ref", "sort", "order", "snapshot_ref"))
    scope = RunCandidateReadScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                  request.args.get("batch_ref"), request.args.get("sort", "sequence"), request.args.get("order", "asc"))
    token = request.args.get("snapshot_ref")
    binding = resolve_read_snapshot(token) if token is not None else None
    # 整份候选加正式计划基线一起重建，和看板、现场页一起排读额度。
    with PLAN_READ_SLOTS.slot():
        data, state = read_candidate_comparison(g.db, scope)
    snapshot = bind_read_snapshot({**scope.scope(), "kind": "dashboard-candidate-comparison"}, state, token, binding=binding)
    return _response(data, snapshot)
