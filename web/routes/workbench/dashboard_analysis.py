"""Dashboard-only GET adapters; no command, worker or adoption registration."""

from flask import g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.dashboard_analysis import read_dashboard_analysis
from core.services.workbench.dashboard_candidate_comparison import read_candidate_comparison

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .run_candidates import _response


def _arguments(allowed):
    if set(request.args) - set(allowed) or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "分析的查询条件有重复或不支持的项，当前范围没有变化。请点「刷新分析」后重试。", 400)


@api_endpoint
def dashboard_analysis():
    _arguments(("plan_ref", "snapshot_ref"))
    plan_ref = request.args.get("plan_ref")
    data, state = read_dashboard_analysis(g.db, plan_ref)
    snapshot = bind_read_snapshot({"kind": "dashboard-analysis", "plan_ref": plan_ref}, state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


@api_endpoint
def dashboard_candidate_comparison(candidate_ref):
    _arguments(("range_start", "range_end", "batch_ref", "sort", "order", "snapshot_ref"))
    scope = RunCandidateReadScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                  request.args.get("batch_ref"), request.args.get("sort", "sequence"), request.args.get("order", "asc"))
    data, state = read_candidate_comparison(g.db, scope)
    snapshot = bind_read_snapshot({**scope.scope(), "kind": "dashboard-candidate-comparison"}, state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)
