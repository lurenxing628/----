"""Shared receipt lookup endpoint for ordinary SQLite workbench commands."""

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.commands import WorkbenchCommandService, command_lookup_payload
from web.api_responses import json_response

from .api_responses import api_endpoint


@api_endpoint
def command_receipt(request_key):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "查询保存结果时不需要其他筛选条件。请直接点「查询结果」。", 400)
    receipt = WorkbenchCommandService(g.db, current_app.logger).lookup(request_key)
    return json_response(command_lookup_payload(receipt))


def register_command_routes(bp):
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt, methods=["GET"])
