"""Explicit registration hook; the main integrator owns enabling this slice."""

from flask import current_app, g, request

from core.models.workbench_calibration import MAX_RESPONSE_BYTES
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.calibration.adoption import WorkbenchCalibrationAdoptionService
from core.services.workbench.commands import command_lookup_payload
from core.shared.key_sets import keys_conform
from web.api_responses import json_response, query_success
from web.runtime_host import wall_clock

from .api_responses import api_endpoint, read_endpoint
from .read_context import unbound_snapshot
from .request_json import BodyTexts, command_body, read_json_body, rejecter
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchCalibrationAdoptionService(g.db,
        integration_enabled=current_app.config.get("WORKBENCH_CALIBRATION_ADOPTION_ENABLED") is True,
        context_factory=issue_write_context, context_validator=validate_write_context, clock=wall_clock(current_app))


_REJECTED = "提交的内容不完整或有多余项，还没有采用。请刷新页面后重新填写。"
_BODY = BodyTexts(transport=_REJECTED, malformed=_REJECTED, incomplete=_REJECTED)


@read_endpoint
def calibration_adoption_preview(suggestion_ref):
    value = read_json_body(_BODY)
    if not keys_conform(value, ("input",)):
        rejecter(_REJECTED)()
    data = _service().preview(suggestion_ref, value["input"])
    # 采用预览靠写入凭据防并发，没有可回绑的读取快照。
    return query_success(data, unbound_snapshot(data["generated_at"]), byte_limit=MAX_RESPONSE_BYTES,
        too_large_message="这次要读的采用明细超过 8 MB，还没有采用。请缩小范围后重试。")


@api_endpoint
def calibration_adoption_confirm(suggestion_ref):
    value = command_body(_BODY, stale="本页数据已过期，还没有采用。请刷新页面后重新填写。")
    g.workbench_result_target = (
        "/api/workbench/v1/calibration/" + suggestion_ref + "/adopt/receipts/" + value["request_key"]
    )
    result = _service().confirm(suggestion_ref, value["write_token"], value["request_key"], value["input"])
    return json_response(result)


@api_endpoint
def calibration_adoption_receipt(suggestion_ref, request_key):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "查询保存结果时不需要其他筛选条件。请直接点「查询结果」。", 400)
    result = _service().receipt(suggestion_ref, request_key)
    return json_response(command_lookup_payload(result))


def register_calibration_adoption_routes(bp):
    base = "/api/workbench/v1/calibration/<suggestion_ref>"
    bp.add_url_rule(base + "/adopt-preview", view_func=calibration_adoption_preview, methods=["POST"])
    bp.add_url_rule(base + "/adopt", view_func=calibration_adoption_confirm, methods=["POST"])
    bp.add_url_rule(base + "/adopt/receipts/<request_key>", view_func=calibration_adoption_receipt, methods=["GET"])
