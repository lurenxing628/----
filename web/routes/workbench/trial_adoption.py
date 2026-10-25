"""Explicit scenario adoption routes, using the existing managed adoption gate."""

from flask import current_app, g, request

from core.models.workbench_command import validate_request_key
from core.models.workbench_trial import fields, reject
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint, read_endpoint
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    from core.services.workbench.facts.run_data_context import RunDataContext
    from core.services.workbench.trial.adoption import WorkbenchTrialAdoptionService

    return WorkbenchTrialAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CANDIDATE_ADOPTION_ENABLED") is True,
        point_rendering_enabled=current_app.config.get("WORKBENCH_POINT_RENDERING_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context,
        data_context=RunDataContext(g.db, current_app.config.get("WORKBENCH_SYSTEM_JOURNAL_DIR"),
                                   current_app.config.get("BACKUP_DIR")))


def _body(required):
    if request.args:
        reject("invalid_input", "提交的内容格式不正确，试调方案还没有采用。请刷新页面后重新点「确认正式采用」。", 400)
    value = request.get_json()
    fields(value, required)
    return value


def _query(data, scope):
    response = query_success(data, bind_read_snapshot(scope, data, None))
    response.headers["Cache-Control"] = "no-store"
    return response


@read_endpoint
def trial_adopt_preview(scenario_ref):
    _body(())
    return _query(_service().preview(scenario_ref), {"scenario_ref": scenario_ref, "action": "adopt-preview"})


@api_endpoint
def trial_adopt(scenario_ref):
    value = _body(("write_token", "request_key", "input"))
    validate_request_key(value["request_key"])
    g.workbench_request_key = value["request_key"]
    g.workbench_result_target = "/api/workbench/v1/trial/scenarios/" + scenario_ref + "/adoption-commands/" + value["request_key"]
    response = json_response(_service().adopt(scenario_ref, value["write_token"], value["request_key"], value["input"]))
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_adoption_receipt(scenario_ref, request_key):
    if set(request.args) - {"data_context_ref"} or any(len(values) != 1 for _, values in request.args.lists()):
        reject("invalid_input", "查询采用结果的条件有多余项或重复项，请重新查询。", 400)
    result = _service().resolve_command(scenario_ref, request_key, data_context_ref=request.args.get("data_context_ref"))
    return _query(result,
                  {"scenario_ref": scenario_ref, "request_key": request_key})


def register_trial_adoption_routes(bp):
    base = "/api/workbench/v1/trial/scenarios/<scenario_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=trial_adopt_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=trial_adopt, methods=["POST"])
    bp.add_url_rule(base + "/adoption-commands/<request_key>", view_func=trial_adoption_receipt, methods=["GET"])
