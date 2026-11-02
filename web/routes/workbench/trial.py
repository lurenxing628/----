"""Coordinator hook only; JSON trial commands never register or publish a plan."""

import re

from flask import g, request

from core.models.content import content_text
from core.models.workbench_command import validate_request_key
from core.models.workbench_trial import create_input, fields, reference
from core.models.workbench_trial_catalog import TrialCatalogScope
from core.services.workbench import messages
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.source_revisions import TRIAL_SOURCE_KEYS, read_source_revisions
from core.services.workbench.trial.catalog import WorkbenchTrialCatalogService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint, read_endpoint
from .data_context import request_data_context
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _service():
    from core.services.workbench.trial.service import WorkbenchTrialService

    return WorkbenchTrialService(
        g.db,
        context_factory=issue_write_context,
        context_validator=validate_write_context,
        data_context=request_data_context(),
    )


def _body(command=False):
    if request.args:
        from core.models.workbench_trial import reject
        reject("invalid_input", "提交的内容格式不正确，试调还没有保存。请刷新页面后重新填写。", 400)
    value = request.get_json()
    if command:
        fields(value, ("request_key", "write_token", "input"))
        validate_request_key(value["request_key"])
        g.workbench_request_key = value["request_key"]
        g.workbench_result_target = "/api/workbench/v1/trial/commands/" + value["request_key"]
    return value


def _query(read, scope, *, data_context, precheck=None):
    allowed = {"snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        from core.models.workbench_trial import reject
        reject("invalid_input", messages.STALE, 400)
    with candidate_read_snapshot(g.db):
        checked = precheck() if precheck is not None else None
        state = {
            "revisions": read_source_revisions(g.db, TRIAL_SOURCE_KEYS),
            "data_context_ref": data_context.ref(),
        }
        snapshot = bind_read_snapshot(scope, content_text(state), request.args.get("snapshot_ref"))
        data = read(checked) if precheck is not None else read()
    return query_success(data, snapshot)


@read_endpoint
def trial_create_preview():
    intent = create_input(_body())
    service = _service()
    return _query(lambda: service.preview_create(intent), {"kind": "trial_create_preview"},
                  data_context=service.data_context)


@api_endpoint
def trial_create():
    value = _body(True)
    return json_response(_service().create(value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_read(draft_ref):
    reference(draft_ref)
    service = _service()
    return _query(
        lambda header: service.get(draft_ref, header=header),
        {"draft_ref": draft_ref},
        data_context=service.data_context,
        precheck=lambda: service.require_draft_header(draft_ref),
    )


@api_endpoint
def trial_change(draft_ref):
    value = _body(True)
    return json_response(_service().change(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_save(draft_ref):
    value = _body(True)
    return json_response(_service().save(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_discard(draft_ref):
    value = _body(True)
    return json_response(_service().discard(draft_ref, value["input"], value["write_token"], value["request_key"]))


@api_endpoint
def trial_scenario(scenario_ref):
    reference(scenario_ref)
    service = _service()
    return _query(
        lambda header: service.scenario(scenario_ref, header=header),
        {"scenario_ref": scenario_ref},
        data_context=service.data_context,
        precheck=lambda: service.require_scenario_header(scenario_ref),
    )


@api_endpoint
def trial_receipt(request_key):
    validate_request_key(request_key)
    service = _service()
    return _query(
        lambda result: {
            "state": "committed" if result else "not_observed",
            "receipt": result,
            "can_retry_automatically": False,
        },
        {"request_key": request_key},
        data_context=service.data_context,
        precheck=lambda: service.lookup(request_key),
    )


def _catalog(collection):
    from core.models.workbench_trial import reject

    allowed = {"page", "size", "status", "base_kind", "base_ref", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        reject("invalid_input", "试调列表的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。", 400)
    numbers = {}
    for key, default in (("page", "1"), ("size", "20")):
        raw = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,5}", raw) is None:
            reject("invalid_input", "页码或每页数量填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
        numbers[key] = int(raw)
    scope = TrialCatalogScope(collection, status=request.args.get("status", "all"),
        base_kind=request.args.get("base_kind"), base_ref=request.args.get("base_ref"), **numbers)
    data, snapshot = WorkbenchTrialCatalogService(g.db).catalog(
        scope,
        bind_snapshot=lambda content: bind_read_snapshot(scope.scope(), content, request.args.get("snapshot_ref")),
    )
    return query_success(data, snapshot)


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
