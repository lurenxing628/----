"""Explicit BU-only route hook. The application owner registers it separately."""

from flask import g, request

from core.models.workbench_run_baseline import RunCandidateBaselineScope
from core.services.workbench.run.candidate_baseline import WorkbenchRunCandidateBaselineQueryService

from .api_responses import api_endpoint
from .read_context import snapshot_binder
from .request_json import single_value_arguments
from .run_candidates import ARGUMENTS_REJECTED, WORKSPACE_ARGS, candidate_response


@api_endpoint
def run_candidate_baseline(candidate_ref):
    single_value_arguments(WORKSPACE_ARGS, message=ARGUMENTS_REJECTED)
    scope = RunCandidateBaselineScope(candidate_ref, request.args.get("range_start"), request.args.get("range_end"),
                                      request.args.get("batch_ref"), request.args.get("sort", "sequence"),
                                      request.args.get("order", "asc"))
    return candidate_response(*WorkbenchRunCandidateBaselineQueryService(g.db).baseline(
        scope, bind_snapshot=snapshot_binder(request.args.get("snapshot_ref"))))


def register_run_candidate_baseline_routes(bp):
    bp.add_url_rule("/api/workbench/v1/scheduling/candidates/<candidate_ref>/baseline",
                    view_func=run_candidate_baseline, methods=["GET"])
