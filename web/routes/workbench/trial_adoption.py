"""Explicit scenario adoption routes, using the existing managed adoption gate."""

import uuid

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandUncertain, input_fingerprint, validate_request_key
from core.models.workbench_trial import fields, reject
from core.services.workbench.trial_adoption import WorkbenchTrialAdoptionService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchTrialAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CANDIDATE_ADOPTION_ENABLED") is True,
        point_rendering_enabled=current_app.config.get("WORKBENCH_POINT_RENDERING_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context)


def _body(required):
    if request.args:
        reject("invalid_input", "提交的内容格式不正确，试调方案还没有采用。请刷新页面后重新点「确认正式采用」。", 400)
    value = request.get_json()
    fields(value, required)
    return value


def _query(data, scope):
    response = query_success(data, bind_read_snapshot(scope, input_fingerprint(data), None))
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_adopt_preview(scenario_ref):
    _body(())
    return _query(_service().preview(scenario_ref), {"scenario_ref": scenario_ref, "action": "adopt-preview"})


@api_endpoint
def trial_adopt(scenario_ref):
    value = _body(("write_token", "request_key", "input"))
    validate_request_key(value["request_key"])
    g.workbench_request_key = value["request_key"]
    try:
        result = _service().adopt(scenario_ref, value["write_token"], value["request_key"], value["input"])
    except WorkbenchCommandUncertain as exc:
        current_app.logger.exception("场景采用提交结果待核实 request_key=%s", exc.request_key)
        response = jsonify({"ok": False, "committed": "unknown", "error": {
            "code": "storage_failure", "message": str(exc), "fields": [], "retryable": False,
            "request_ref": uuid.uuid4().hex, "request_key": exc.request_key,
            "result_target": "/api/workbench/v1/trial/scenarios/" + scenario_ref + "/adoption-commands/" + exc.request_key}})
        response.status_code = 500
    else:
        response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_adoption_receipt(scenario_ref, request_key):
    if request.args:
        reject("invalid_input", "查询采用结果时不需要其他筛选条件。请直接点「查询结果」。", 400)
    result = _service().lookup(scenario_ref, request_key)
    return _query({"state": "committed" if result else "not_observed", "receipt": result,
                   "may_be_in_flight": result is None, "can_retry_automatically": False},
                  {"scenario_ref": scenario_ref, "request_key": request_key})


def register_trial_adoption_routes(bp):
    base = "/api/workbench/v1/trial/scenarios/<scenario_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=trial_adopt_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=trial_adopt, methods=["POST"])
    bp.add_url_rule(base + "/adoption-commands/<request_key>", view_func=trial_adoption_receipt, methods=["GET"])
