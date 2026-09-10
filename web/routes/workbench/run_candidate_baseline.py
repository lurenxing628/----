"""Explicit BU-only route hook. The application owner registers it separately."""

from flask import g, request

from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.services.workbench.run_candidate_baseline import WorkbenchRunCandidateBaselineQueryService

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .run_candidates import _WORKSPACE_ARGS, _arguments, _response


@api_endpoint
def run_candidate_baseline(candidate_ref):
    _arguments(_WORKSPACE_ARGS)
    scope = RunCandidateBaselineScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                      request.args.get("batch_ref"), request.args.get("sort", "sequence"),
                                      request.args.get("order", "asc"))
    data, state = WorkbenchRunCandidateBaselineQueryService(g.db).baseline(scope)
    snapshot = bind_read_snapshot(scope.scope(), state, request.args.get("snapshot_ref"))
    return _response(data, snapshot)


def register_run_candidate_baseline_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/candidates/<candidate_ref>/baseline",
                    view_func=run_candidate_baseline, methods=["GET"])
