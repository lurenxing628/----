"""Explicit registration hook; the main integrator owns enabling this slice."""

from flask import current_app, g, jsonify, request

from core.models.workbench_calibration import MAX_RESPONSE_BYTES
from core.models.workbench_command import WorkbenchCommandRejected
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
        raise WorkbenchCommandRejected("invalid_input", "采纳请求字段缺失，或包含未知字段、重复范围。", 400)
    return value


@api_endpoint
def calibration_adoption_preview(suggestion_ref):
    value = _body(("input",))
    data = _service().preview(suggestion_ref, value["input"])
    response = query_success(data, {"as_of": data["generated_at"]})
    if len(response.get_data()) > MAX_RESPONSE_BYTES:
        raise WorkbenchCommandRejected("query_too_large", "完整采纳预览超过8MB，请缩小范围后重试。", 413)
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
        raise WorkbenchCommandRejected("invalid_input", "回执查询不接受额外筛选参数。", 400)
    result = _service().receipt(suggestion_ref, request_key)
    if result is None:
        raise WorkbenchCommandRejected("receipt_not_found", "尚未查到已提交回执；在途请求仍可能完成，重试必须保留原请求标识。", 404)
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_calibration_adoption_routes(bp):
    base = "/api/workbench/v1/calibration/<suggestion_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=calibration_adoption_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=calibration_adoption_confirm, methods=["POST"])
    bp.add_url_rule(base + "/adopt/receipts/<request_key>", view_func=calibration_adoption_receipt, methods=["GET"])
