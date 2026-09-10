"""Explicit coordinator registration only; ordinary candidate GETs stay read-only."""

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.services.workbench.run_candidate_adoption import WorkbenchRunCandidateAdoptionService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchRunCandidateAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CANDIDATE_ADOPTION_ENABLED") is True,
        point_rendering_enabled=current_app.config.get("WORKBENCH_POINT_RENDERING_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context)


def _body(fields):
    value = request.get_json()
    if request.args or type(value) is not dict or set(value) != set(fields):
        raise WorkbenchCommandRejected("invalid_input", "采用请求字段缺失、重复范围或含未知内容。", 400)
    return value


@api_endpoint
def run_candidate_adopt_preview(candidate_ref):
    _body(())
    data = _service().preview(candidate_ref)
    snapshot = bind_read_snapshot({"candidate_ref": candidate_ref, "action": "adopt-preview"}, input_fingerprint(data), None)
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def run_candidate_adopt(candidate_ref):
    value = _body(("write_token", "request_key", "input"))
    g.workbench_request_key = value["request_key"]
    result = _service().adopt(candidate_ref, value["write_token"], value["request_key"], value["input"])
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_run_candidate_adoption_routes(bp):
    base = "/api/workbench/v1/scheduling/candidates/<candidate_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=run_candidate_adopt_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=run_candidate_adopt, methods=["POST"])
