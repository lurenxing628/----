"""Read and update default work periods without changing per-date overrides."""

from flask import current_app, g, jsonify, request

from core.infrastructure.transaction import TransactionManager
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint, validate_request_key
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource.calendar_defaults import WorkbenchCalendarDefaultsService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot
from .resource_action_context import json_body
from .write_context import issue_write_context, validate_write_context

SUBJECT, ACTION = "calendar-defaults", "calendar.defaults"


@api_endpoint
def calendar_defaults_read():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "默认工作时间读取条件不正确。", 400)
    with TransactionManager(g.db).transaction():
        state = WorkbenchCalendarDefaultsService(g.db).snapshot()
        context = issue_write_context(SUBJECT, [ACTION], state)
        snapshot = bind_read_snapshot({"kind": "calendar_defaults"}, input_fingerprint(state))
    return query_success({"periods": state["periods"], "hours": state["hours"], "write_context": context}, snapshot)


@api_endpoint
def calendar_defaults_write():
    body = json_body({"request_key", "write_token", "input"})
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    service = WorkbenchCalendarDefaultsService(g.db)
    payload = service.normalize(body["input"])

    def guard():
        state = service.snapshot()
        validate_write_context(body["write_token"], SUBJECT, ACTION, state)
        return state

    result = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=ACTION, context_ref=SUBJECT, normalized_input=payload,
        guard=guard, mutate=lambda state: service._apply_checked(payload, state))
    return jsonify(result)


def register_calendar_defaults_routes(bp):
    bp.add_url_rule("/api/workbench/v1/calendar/defaults", view_func=calendar_defaults_read, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/calendar/defaults", view_func=calendar_defaults_write, methods=["POST"])
