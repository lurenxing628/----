"""Dashboard-only GET adapters; no command, worker or adoption registration."""

from flask import g, request

from core.models.workbench_dashboard import MAX_BYTES, DashboardAnalysisQuery
from core.models.workbench_run_candidate import RunCandidateReadScope
from core.services.workbench.dashboard.analysis import read_dashboard_analysis
from core.services.workbench.run.candidate_comparison import read_candidate_comparison
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, page_integer, read_snapshot_time
from .request_json import single_value_arguments


def _response(data, snapshot):
    return query_success(data, snapshot, byte_limit=MAX_BYTES)


_ARGUMENTS_REJECTED = "分析的查询条件有重复或不支持的项，当前范围没有变化。请点「刷新分析」后重试。"


@api_endpoint
def dashboard_analysis():
    single_value_arguments(("plan_ref", "section", "page", "size", "resource_ref", "locate_batch_ref", "snapshot_ref"), message=_ARGUMENTS_REJECTED)
    plan_ref = request.args.get("plan_ref")
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        value = request.args.get(key, default)
        numbers[key] = page_integer(value, message="影响分析的页码或每页数量无效。")
    query = DashboardAnalysisQuery(request.args.get("section", "delivery"), numbers["page"], numbers["size"],
                                   request.args.get("resource_ref"), request.args.get("locate_batch_ref"))
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    bound = {}
    with PLAN_READ_SLOTS.slot():
        data, _ = read_dashboard_analysis(
            g.db,
            plan_ref,
            query=query,
            as_of=as_of,
            binding=binding,
            bind_snapshot=lambda state, resolved_as_of, revisions: bound.setdefault(
                "snapshot",
                bind_read_snapshot(query.scope(plan_ref), state, token, as_of=resolved_as_of, binding=binding,
                                   revisions=revisions),
            ),
        )
    return _response(data, bound["snapshot"])


@api_endpoint
def dashboard_candidate_comparison(candidate_ref):
    single_value_arguments(("range_start", "range_end", "batch_ref", "sort", "order", "snapshot_ref"), message=_ARGUMENTS_REJECTED)
    scope = RunCandidateReadScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                  request.args.get("batch_ref"), request.args.get("sort", "sequence"), request.args.get("order", "asc"))
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    # 整份候选加正式计划基线一起重建，和看板、现场页一起排读额度。
    with PLAN_READ_SLOTS.slot():
        data, snapshot = read_candidate_comparison(
            g.db, scope, bind_snapshot=lambda read_scope, state: bind_read_snapshot(read_scope, state, token, as_of=as_of,
                                                                                     binding=binding))
    return _response(data, snapshot)
