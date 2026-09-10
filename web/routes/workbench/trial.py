"""Coordinator hook only; JSON trial commands never register or publish a plan."""

import re
import uuid

from flask import g, jsonify, request

from core.models.workbench_command import WorkbenchCommandUncertain, input_fingerprint
from core.models.workbench_trial import fields
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench.trial import WorkbenchTrialService
from core.services.workbench.trial_catalog import WorkbenchTrialCatalogService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    return WorkbenchTrialService(g.db, context_factory=issue_write_context, context_validator=validate_write_context)


def _body(command=False):
    if request.args:
        from core.models.workbench_trial import reject
        reject("invalid_input", "试调写请求不能在URL中叠加范围或参数。", 400)
    value = request.get_json()
    if command:
        fields(value, ("request_key", "write_token", "input"))
        g.workbench_request_key = value["request_key"]
    return value


def _query(data, scope):
    allowed = {"snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        from core.models.workbench_trial import reject
        reject("invalid_input", "草稿读取只接受原快照引用，不重新筛选或切换基础计划。", 400)
    response = query_success(data, bind_read_snapshot(scope, input_fingerprint(data), request.args.get("snapshot_ref")))
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_create_preview():
    return _query(_service().preview_create(_body()), {"kind": "trial_create_preview"})


def _command(call):
    try:
        result = call()
    except WorkbenchCommandUncertain as exc:
        response = jsonify({"ok": False, "committed": "unknown", "error": {
            "code": "storage_failure", "message": str(exc), "fields": [], "retryable": False,
            "request_ref": uuid.uuid4().hex,
            "request_key": exc.request_key, "result_target": "/api/workbench/v1/trial/commands/" + exc.request_key}})
        response.status_code = 500
    else:
        response = jsonify(result)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_create():
    value = _body(True)
    return _command(lambda: _service().create(value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_read(draft_ref):
    return _query(_service().get(draft_ref), {"draft_ref": draft_ref})


@api_endpoint
def trial_change(draft_ref):
    value = _body(True)
    return _command(lambda: _service().change(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_save(draft_ref):
    value = _body(True)
    return _command(lambda: _service().save(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_discard(draft_ref):
    value = _body(True)
    return _command(lambda: _service().discard(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_scenario(scenario_ref):
    return _query(_service().scenario(scenario_ref), {"scenario_ref": scenario_ref})


@api_endpoint
def trial_receipt(request_key):
    result = _service().lookup(request_key)
    return _query({"state": "committed" if result else "not_observed", "receipt": result,
                   "can_retry_automatically": False}, {"request_key": request_key})


def _catalog(collection):
    from core.models.workbench_trial import reject

    allowed = {"page", "size", "status", "base_kind", "base_ref", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("invalid_input", "目录查询含未知或重复参数，未忽略筛选。", 400)
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        raw = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,5}", raw) is None:
            reject("invalid_input", "目录页码与每页数量必须为正整数。", 400)
        numbers[key] = int(raw)
    scope = TrialCatalogScope(collection, status=request.args.get("status", "all"),
        base_kind=request.args.get("base_kind"), base_ref=request.args.get("base_ref"), **numbers)
    data, digest = WorkbenchTrialCatalogService(g.db).catalog(scope)
    response = query_success(data, bind_read_snapshot(scope.scope(), digest, request.args.get("snapshot_ref")))
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def trial_drafts():
    return _catalog("drafts")


@api_endpoint
def trial_scenarios():
    return _catalog("scenarios")


def register_trial_routes(bp):
    base = "/api/workbench/v1/trial"
    for suffix, function, methods in (
        ("/drafts", trial_drafts, ["GET"]), ("/scenarios", trial_scenarios, ["GET"]),
        ("/drafts/preview", trial_create_preview, ["POST"]), ("/drafts", trial_create, ["POST"]),
        ("/drafts/<draft_ref>", trial_read, ["GET"]), ("/drafts/<draft_ref>/change", trial_change, ["POST"]),
        ("/drafts/<draft_ref>/save", trial_save, ["POST"]), ("/drafts/<draft_ref>/discard", trial_discard, ["POST"]),
        ("/scenarios/<scenario_ref>", trial_scenario, ["GET"]), ("/commands/<request_key>", trial_receipt, ["GET"]),
    ):
        bp.add_url_rule(base + suffix, view_func=function, methods=methods)
