"""Exclusive route hook. Mainline owns registration, receipt endpoint and schema."""

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_dashboard import MAX_BYTES, DashboardQuery
from core.services.workbench import messages
from core.services.workbench.dashboard.commands import WorkbenchDashboardCommandService
from core.services.workbench.dashboard.service import WorkbenchDashboardService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .dashboard_analysis import dashboard_analysis, dashboard_candidate_comparison
from .read_budget import PLAN_READ_SLOTS
from .read_context import bind_read_snapshot, page_integer, read_snapshot_time
from .write_context import issue_write_context, validate_write_context


def _arguments(detail, history):
    allowed = {"category", "status", "query", "sort", "direction", "page", "size", "source", "snapshot_ref"}
    if history:
        allowed.add("history_page")
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "值班台的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    numbers = {}
    for key, default in (("page", "1"), ("size", "20"), ("history_page", "1")):
        value = request.args.get(key, default)
        numbers[key] = page_integer(value)
    query = DashboardQuery(**{key: value for key, value in request.args.items() if key not in
                              ("page", "size", "snapshot_ref", "history_page")}, number=numbers["page"], size=numbers["size"])
    token = request.args.get("snapshot_ref")
    if detail and not token:
        raise WorkbenchCommandRejected("snapshot_required", messages.STALE, 400)
    return query, token, numbers["history_page"]


def _history(reader, item_ref, number, size):
    """Read history in the same snapshot, but report it only after the item is known to be in scope."""
    try:
        return reader.history(item_ref, number, size), None
    except WorkbenchCommandRejected as exc:
        return None, exc


def _read(item_ref=None, history=False):
    query, token, history_page = _arguments(item_ref is not None, history)
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchDashboardService(g.db, context_factory=issue_write_context)
    admission = PLAN_READ_SLOTS.slot(lane=request.headers.get("X-Workbench-Read-Lane")) if item_ref is None else PLAN_READ_SLOTS.slot()
    with admission:
        with reader.read_snapshot():
            sources = reader.load(as_of)
            records = _history(reader, item_ref, history_page, query.size) if history else None
        # 读事务到此结束：整份看板的投影和指纹只用已读出的事实，算多久都不挡别人提交写入。
        data = reader.project(sources)
        analysis, analysis_error = None, None
        if item_ref is None:
            try:
                analysis = reader.analysis(sources)
            except WorkbenchCommandRejected as exc:
                analysis_error = str(exc)
            except Exception:
                current_app.logger.exception("Dashboard analysis failed after the list was read")
                analysis_error = "分析数据没有读出来，请刷新重试。"
    snapshot = bind_read_snapshot(query.scope(), data["snapshot_contents"], token,
                                  as_of=data["as_of"], binding=binding)
    if item_ref is None:
        result = reader.workspace(data, query)
        result["analysis"] = analysis
        result["analysis_error"] = analysis_error
    else:
        item = reader.detail(data, item_ref, query)
        result = {"item": reader.public_item(item), "as_of": data["as_of"], "scope": query.scope()}
        if records is not None:
            result["history"], error = records
            if error is not None:
                raise error
    response = query_success(result, snapshot, byte_limit=MAX_BYTES)
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
        raise WorkbenchCommandRejected("invalid_input", "提交的内容格式不正确，处置还没有保存。请刷新页面后重新填写。", 400)
    body = request.get_json()
    if type(body) is not dict or set(body) != {"request_key", "write_token", "input"} or type(body["input"]) is not dict:
        raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，处置还没有保存。请刷新页面后重新填写。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    service = WorkbenchDashboardCommandService(g.db)
    result = service.execute(action, item_ref, body["input"], request_key=body["request_key"], admission=PLAN_READ_SLOTS.slot,
        validate_context=lambda subject, verb, facts: validate_write_context(body["write_token"], subject, verb, facts))
    response = json_response(result)
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
