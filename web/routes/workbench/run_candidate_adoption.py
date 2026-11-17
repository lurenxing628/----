"""Explicit coordinator registration only; ordinary candidate GETs stay read-only."""

from flask import current_app, g

from core.models.workbench_run_job import validate_run_ref
from core.shared.key_sets import keys_conform
from web.api_responses import json_response, query_success
from web.runtime_host import wall_clock

from .api_responses import api_endpoint, read_endpoint
from .data_context import request_data_context
from .read_context import current_snapshot_time, unbound_snapshot
from .request_json import BodyTexts, command_body, read_json_body, rejecter, single_value_arguments
from .write_context import issue_write_context, validate_write_context


def _service():
    from core.services.workbench.run.candidate_adoption import WorkbenchRunCandidateAdoptionService

    return WorkbenchRunCandidateAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CANDIDATE_ADOPTION_ENABLED") is True,
        point_rendering_enabled=current_app.config.get("WORKBENCH_POINT_RENDERING_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context,
        data_context=request_data_context(), clock=wall_clock(current_app))


_REJECTED = "提交的内容不完整或有多余项，还没有采用。请刷新页面后重新点「确认正式采用」。"
_BODY = BodyTexts(transport=_REJECTED, malformed=_REJECTED, incomplete=_REJECTED)


@read_endpoint
def run_candidate_adopt_preview(candidate_ref):
    if not keys_conform(read_json_body(_BODY), ()):
        rejecter(_REJECTED)()
    as_of = current_snapshot_time()
    data = _service().preview(candidate_ref)
    return query_success(data, unbound_snapshot(as_of))


@api_endpoint
def run_candidate_adopt(candidate_ref):
    value = command_body(_BODY, stale="本页数据已过期，还没有采用。请刷新页面后重新点「确认正式采用」。")
    validate_run_ref(candidate_ref)
    g.workbench_result_target = (
        "/api/workbench/v1/scheduling/candidates/" + candidate_ref + "/adoption-commands/" + value["request_key"]
    )
    result = _service().adopt(candidate_ref, value["write_token"], value["request_key"], value["input"])
    return json_response(result)


@api_endpoint
def run_candidate_adoption_command(candidate_ref, request_key):
    arguments = single_value_arguments({"run_ref", "data_context_ref"}, required={"data_context_ref"},
                                       message="查询采用结果的条件不完整、有多余项或重复项，请重新查询。")
    result = _service().resolve_command(candidate_ref, request_key, run_ref=arguments.get("run_ref"),
                                        data_context_ref=arguments["data_context_ref"])
    return json_response(result)


def register_run_candidate_adoption_routes(bp):
    base = "/api/workbench/v1/scheduling/candidates/<candidate_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=run_candidate_adopt_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=run_candidate_adopt, methods=["POST"])
    bp.add_url_rule(base + "/adoption-commands/<request_key>", view_func=run_candidate_adoption_command, methods=["GET"])
