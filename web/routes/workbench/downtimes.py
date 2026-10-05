"""Single-machine downtime read and idempotent write routes."""

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint, validate_request_key
from core.models.workbench_downtime import normalize_downtime
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.downtimes import WorkbenchDowntimeService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .resource_action_context import json_body
from .write_context import issue_write_context, validate_write_context

ACTIONS = ["machine.downtime_" + action for action in ("create", "update", "cancel")]


@api_endpoint
def machine_downtimes(ref):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "停机记录不接受额外查询条件，请重新打开设备详情。", 400)
    service = WorkbenchDowntimeService(g.db, current_app.logger)
    with service.reader.read_snapshot(capture_fingerprint=False):
        state = service.snapshot(ref)
        data = {"entity_ref": ref, **service.public(state), "write_context": issue_write_context(ref, ACTIONS, state)}
        snapshot = bind_read_snapshot({"kind": "machine_downtimes", "ref": ref}, input_fingerprint(state))
    return query_success(data, snapshot)


@api_endpoint
def machine_downtime_command(ref, action):
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    payload = normalize_downtime(action, body["input"])
    service = WorkbenchDowntimeService(g.db, current_app.logger)
    name = "machine.downtime_" + action

    def guard():
        state = service.snapshot(ref)
        validate_write_context(body["write_token"], ref, name, state)
        return state

    return jsonify(WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=name, context_ref=ref, normalized_input=payload,
        guard=guard, mutate=lambda state: service.apply(ref, action, payload, state)))


def register_downtime_routes(bp):
    base = "/api/workbench/v1/entities/machine/<ref>/downtimes"
    bp.add_url_rule(base, view_func=machine_downtimes, methods=["GET"])
    for action in ("create", "update", "cancel"):
        bp.add_url_rule(base + "/" + action, endpoint="machine_downtime_" + action, view_func=machine_downtime_command,
                        defaults={"action": action}, methods=["POST"])
