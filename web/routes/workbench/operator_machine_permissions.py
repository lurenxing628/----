"""Personnel machine permission preview and confirmation routes."""

from flask import current_app, g

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.operator_machine_permissions import OPERATION, WorkbenchOperatorMachinePermissions
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .resource_action_context import EXPIRED_MESSAGE, json_body, opaque_ref, read_endpoint
from .write_context import preview_write_context, resolve_action_preview, retain_action_preview, validate_write_context

SCOPE = "workbench-operator-machine-permissions-v1"
_MISMATCH_MESSAGE = "预检与所选人员不一致，请重新预检。"


@read_endpoint
def operator_machine_preview(ref):
    body = json_body({"machine_permissions", "write_token"})
    service = WorkbenchOperatorMachinePermissions(g.db, current_app.logger)
    with service.reader.read_snapshot() as fingerprint:
        preview = service.preview(ref, body["machine_permissions"])
        value = preview.as_dict()
        validate_write_context(body["write_token"], ref, "operator.update", value["request"]["expected_operator"])
        preview_ref, expiry = retain_action_preview(SCOPE, preview)
        data = {"operator_ref": ref, "preview_ref": preview_ref, "expires_at": expiry,
                "rows": value["rows"], "summary": value["summary"], "commit_policy": "atomic",
                "write_context": preview_write_context(preview_ref, expiry, [OPERATION])}
        snapshot = bind_read_snapshot({"kind": "operator", "ref": ref, "action": OPERATION}, fingerprint)
    return query_success(data, snapshot)


def _resolve(ref, preview_ref, write_token):
    preview = resolve_action_preview(SCOPE, preview_ref, OPERATION, write_token,
                                     expired_message=EXPIRED_MESSAGE, mismatch_message=_MISMATCH_MESSAGE)
    # The URL names the operator being changed; a preview of another operator must not be confirmed here.
    if preview.as_dict()["request"]["operator_ref"] != ref:
        raise WorkbenchCommandRejected("stale_write", _MISMATCH_MESSAGE)
    return preview


@api_endpoint
def operator_machine_confirm(ref):
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if type(body["input"]) is not dict or set(body["input"]) != {"preview_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "请选择刚才预检的设备关联。", 400)
    preview_ref = opaque_ref(body["input"]["preview_ref"])
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=OPERATION, context_ref=ref, normalized_input={"preview_ref": preview_ref},
        guard=lambda: _resolve(ref, preview_ref, body["write_token"]),
        mutate=lambda preview: WorkbenchOperatorMachinePermissions(g.db, current_app.logger).confirm(preview))
    return json_response(outcome)


def register_operator_machine_routes(bp):
    base = "/api/workbench/v1/entities/operator/<ref>/machine-permissions/"
    bp.add_url_rule(base + "preview", view_func=operator_machine_preview, methods=["POST"])
    bp.add_url_rule(base + "confirm", view_func=operator_machine_confirm, methods=["POST"])
