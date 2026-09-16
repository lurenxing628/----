"""Personnel machine permission preview and confirmation routes."""

from flask import current_app, g, jsonify

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_resource_action import ResourceActionPreview
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.operator_machine_permissions import OPERATION, WorkbenchOperatorMachinePermissions
from core.services.workbench.resource_queries import WorkbenchResourceQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .resource_action_context import json_body, opaque_ref, read_endpoint, resolve_context, retain_context
from .write_context import issue_write_context, validate_write_context

SCOPE = "workbench-operator-machine-permissions-v1"


@read_endpoint
def operator_machine_preview(ref):
    body = json_body({"machine_permissions", "write_token"})
    reader = WorkbenchResourceQueryService(g.db, "operator", current_app.logger)
    with reader.read_snapshot() as fingerprint:
        record = reader.detail(ref)
        validate_write_context(body["write_token"], ref, "operator.update", record.state)
        preview = WorkbenchOperatorMachinePermissions(g.db, current_app.logger).preview(ref, body["machine_permissions"])
        preview_ref, expiry = retain_context(SCOPE, preview.document)
        value = preview.as_dict()
        data = {"operator_ref": ref, "preview_ref": preview_ref, "expires_at": expiry,
                "rows": value["rows"], "summary": value["summary"], "commit_policy": "atomic",
                "write_context": issue_write_context(ref, [OPERATION], preview.intent())}
        snapshot = bind_read_snapshot({"kind": "operator", "ref": ref, "action": OPERATION}, fingerprint)
    return query_success(data, snapshot)


def _resolve(ref, preview_ref, write_token):
    document, _ = resolve_context(SCOPE, preview_ref, "stale_write")
    preview = ResourceActionPreview(document)
    body = preview.as_dict()
    if body["operation"] != OPERATION or body["request"]["operator_ref"] != ref:
        raise WorkbenchCommandRejected("stale_write", "预览与所选人员不一致，请重新预览。")
    validate_write_context(write_token, ref, OPERATION, preview.intent())
    return preview


@api_endpoint
def operator_machine_confirm(ref):
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if type(body["input"]) is not dict or set(body["input"]) != {"preview_ref"}:
        raise WorkbenchCommandRejected("invalid_input", "请选择刚才预览的设备关联。", 400)
    preview_ref = opaque_ref(body["input"]["preview_ref"], "preview_ref")
    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=OPERATION, context_ref=ref, normalized_input={"preview_ref": preview_ref},
        guard=lambda: _resolve(ref, preview_ref, body["write_token"]),
        mutate=lambda preview: WorkbenchOperatorMachinePermissions(g.db, current_app.logger).confirm(preview))
    return jsonify(outcome)


def register_operator_machine_routes(bp):
    base = "/api/workbench/v1/entities/operator/<ref>/machine-permissions/"
    bp.add_url_rule(base + "preview", view_func=operator_machine_preview, methods=["POST"])
    bp.add_url_rule(base + "confirm", view_func=operator_machine_confirm, methods=["POST"])
