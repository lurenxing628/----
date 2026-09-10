"""Exclusive route hook. Mainline owns registration, receipt endpoint and schema."""

import json
from datetime import datetime

from flask import g, jsonify, request

from core.errors import ValidationError
from core.models.workbench_command import WorkbenchCommandRejected, canonical_json, input_fingerprint
from core.models.workbench_dashboard import DashboardQuery, payload_size
from core.services.workbench.dashboard import WorkbenchDashboardService
from core.services.workbench.dashboard_commands import WorkbenchDashboardCommandService
from web.public_token_registry import issue_public_token, resolve_public_token

from .api_responses import api_endpoint, query_success
from .dashboard_analysis import dashboard_analysis, dashboard_candidate_comparison
from .read_context import _SCOPE, bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _arguments(detail, history):
    allowed = {"category", "status", "query", "sort", "direction", "page", "size", "source", "snapshot_ref"}
    if history:
        allowed.add("history_page")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "查询含未知或重复参数，未忽略筛选条件。", 400)
    numbers = {}
    for key, default in (("page", "1"), ("size", "20"), ("history_page", "1")):
        value = request.args.get(key, default)
        if not value.isascii() or not value.isdigit() or not 1 <= len(value) <= 6 or int(value) < 1:
            raise WorkbenchCommandRejected("invalid_input", "页码和每页数量必须是正整数。", 400)
        numbers[key] = int(value)
    query = DashboardQuery(**{key: value for key, value in request.args.items() if key not in
                              ("page", "size", "snapshot_ref", "history_page")}, number=numbers["page"], size=numbers["size"])
    token = request.args.get("snapshot_ref")
    if (detail or query.number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_required", "详情、历史或翻页须携带原列表快照。", 400)
    return query, token, numbers["history_page"]


def _time(token):
    if token is None:
        return datetime.now().replace(microsecond=0)
    try:
        payload = json.loads(resolve_public_token(_SCOPE, token, message="读取快照已失效。", field="snapshot_ref"))
        stamp = payload["as_of"]
        parsed = datetime.fromisoformat(stamp)
        if parsed.tzinfo is not None or parsed.isoformat(timespec="seconds") != stamp:
            raise ValueError()
        return parsed
    except (ValidationError, ValueError, TypeError, KeyError) as exc:
        raise WorkbenchCommandRejected("snapshot_stale", "读取快照已失效，请明确刷新；未自动换范围。") from exc


def _bind(query, data, token):
    if token is not None:
        return bind_read_snapshot(query.scope(), data["fingerprint"], token)
    payload = {"version": 2, "source": "production", "scope_hash": input_fingerprint(query.scope()),
               "fingerprint": data["fingerprint"], "as_of": data["as_of"]}
    return {"snapshot_ref": issue_public_token(_SCOPE, canonical_json(payload), ttl_seconds=900), "as_of": data["as_of"]}


def _read(item_ref=None, history=False):
    query, token, history_page = _arguments(item_ref is not None, history)
    reader = WorkbenchDashboardService(g.db, context_factory=issue_write_context)
    with reader.read_snapshot():
        data = reader.read(_time(token))
        snapshot = _bind(query, data, token)
        if item_ref is None:
            result = reader.workspace(data, query)
        else:
            item = reader.detail(data, item_ref, query)
            result = {"item": reader.public_item(item), "as_of": data["as_of"], "scope": query.scope()}
            if history:
                result["history"] = reader.repo.history(item_ref, history_page, query.size)
            payload_size(result)
    response = query_success(result, snapshot)
    payload_size(response.get_json())
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def dashboard_list():
    return _read()


@api_endpoint
def dashboard_detail(item_ref):
    return _read(item_ref)


@api_endpoint
def dashboard_history(item_ref):
    return _read(item_ref, history=True)


def _command(item_ref, action):
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "处置须提交 JSON CommandInput。", 400)
    body = request.get_json()
    if type(body) is not dict or set(body) != {"request_key", "write_token", "input"} or type(body["input"]) is not dict:
        raise WorkbenchCommandRejected("invalid_input", "处置请求合同不完整或含未知字段。", 400)
    g.workbench_request_key = body["request_key"]
    service = WorkbenchDashboardCommandService(g.db)
    result = service.execute(action, item_ref, body["input"], request_key=body["request_key"],
        validate_context=lambda subject, verb, facts: validate_write_context(body["write_token"], subject, verb, facts))
    response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def dashboard_transition(item_ref):
    return _command(item_ref, "transition")


@api_endpoint
def dashboard_reopen(item_ref):
    return _command(item_ref, "reopen")


def register_dashboard_routes(bp):
    root = "/api/workbench/v1/dashboard"
    for path, function, method in (("", dashboard_list, "GET"), ("/items/<item_ref>", dashboard_detail, "GET"),
                                   ("/analysis", dashboard_analysis, "GET"),
                                   ("/candidates/<candidate_ref>/comparison", dashboard_candidate_comparison, "GET"),
                                   ("/items/<item_ref>/history", dashboard_history, "GET"),
                                   ("/items/<item_ref>/transition", dashboard_transition, "POST"),
                                   ("/items/<item_ref>/reopen", dashboard_reopen, "POST")):
        bp.add_url_rule(root + path, view_func=function, methods=[method])
