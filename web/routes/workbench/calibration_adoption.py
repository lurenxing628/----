"""Explicit registration hook; the main integrator owns enabling this slice."""

from flask import current_app, g, jsonify, request

from core.models.workbench_calibration import MAX_RESPONSE_BYTES
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench import messages
from core.services.workbench.calibration_adoption import WorkbenchCalibrationAdoptionService

from .api_responses import api_endpoint, query_success
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchCalibrationAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CALIBRATION_ADOPTION_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context)


def _body(fields):
    value = request.get_json()
    if request.args or type(value) is not dict or set(value) != set(fields):
        raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，还没有采用。请刷新页面后重新填写。", 400)
    return value


@api_endpoint
def calibration_adoption_preview(suggestion_ref):
    value = _body(("input",))
    data = _service().preview(suggestion_ref, value["input"])
    response = query_success(data, {"as_of": data["generated_at"]})
    if len(response.get_data()) > MAX_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "这次要读的采用明细超过 8 MB，还没有采用。请缩小范围后重试。", 413)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def calibration_adoption_confirm(suggestion_ref):
    value = _body(("write_token", "request_key", "input"))
    g.workbench_request_key = value["request_key"]
    result = _service().confirm(suggestion_ref, value["write_token"], value["request_key"], value["input"])
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def calibration_adoption_receipt(suggestion_ref, request_key):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "查询保存结果时不需要其他筛选条件。请直接点「查询结果」。", 400)
    result = _service().receipt(suggestion_ref, request_key)
    if result is None:
        raise WorkbenchCommandRejected("receipt_not_found", messages.pending("采用"), 404)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_calibration_adoption_routes(bp):
    base = "/api/workbench/v1/calibration/<suggestion_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=calibration_adoption_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=calibration_adoption_confirm, methods=["POST"])
    bp.add_url_rule(base + "/adopt/receipts/<request_key>", view_func=calibration_adoption_receipt, methods=["GET"])
