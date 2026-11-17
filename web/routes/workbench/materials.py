"""First entity API; other resource pages remain unconnected until their contracts land."""

from __future__ import annotations

import re

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from core.services.workbench.material.service import WorkbenchMaterialService, material_action_policy
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot, read_snapshot_time
from .request_json import single_value_arguments
from .write_context import entity_with_context, issue_write_context, subject_command_body, validate_write_context

_COLLECTION = "material:create"


def _services():
    logger = current_app.logger
    return WorkbenchMaterialQueryService(g.db, logger), WorkbenchMaterialService(g.db, logger)


def _page_request():
    allowed = {"query", "status", "page", "size", "sort", "direction", "snapshot_ref"}
    single_value_arguments(allowed, message="物料列表的筛选条件有重复或不支持的项，当前筛选没有变化。请刷新页面后重新选择。")
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码或每页条数填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
        values[key] = int(text)
    return MaterialPageRequest(query=request.args.get("query", ""), status=request.args.get("status") or None,
                               number=values["page"], size=values["size"], sort=request.args.get("sort", "business_code"),
                               direction=request.args.get("direction", "asc"))


def material_entity(record):
    policy = material_action_policy(record.entity["relationships"]["batch_requirement_count"])
    return entity_with_context(record, policy, record.write_state())


@api_endpoint
def material_list():
    scope = _page_request()
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fact_scope:
        snapshot = bind_read_snapshot(scope.scope(), fact_scope.state_fingerprint(), token, as_of=as_of, binding=binding)
        records, page = fact_scope.page(scope)
        data = {"entities": [material_entity(record) for record in records], "page": page, "metrics": fact_scope.metrics(scope),
                "create_context": issue_write_context(_COLLECTION, ["material.create"], None)}
    return query_success(data, snapshot)


@api_endpoint
def material_detail(ref):
    single_value_arguments({"snapshot_ref"}, message="详情的查询条件不对，详情没有打开。请刷新页面后重新点开这一行。")
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot({"kind": "material", "entity_ref": ref}, scope.state_fingerprint(), token,
                                      as_of=as_of, binding=binding)
        entity = material_entity(scope.detail(ref))
    return query_success(entity, snapshot)


@api_endpoint
def material_command(action, ref=None):
    body = subject_command_body("物料")
    reader, domain = _services()
    normalized = domain.normalize_input(action, body["input"])
    subject = _COLLECTION if ref is None else ref
    command = "material." + action

    def guard():
        record = None if action == "create" else reader.detail(ref)
        validate_write_context(body["write_token"], subject, command, None if record is None else record.write_state())
        return domain.prepare_checked(action, normalized, None if record is None else record.state)

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=command, context_ref=subject, normalized_input=normalized,
        guard=guard, mutate=domain.apply_prepared)
    return json_response(outcome)


def register_material_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/material", view_func=material_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/material/<ref>", view_func=material_detail, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/material/create", endpoint="material_create",
                    view_func=material_command, defaults={"action": "create"}, methods=["POST"])
    for action in ("update", "delete"):
        bp.add_url_rule("/api/workbench/v1/entities/material/<ref>/" + action, endpoint="material_" + action,
                        view_func=material_command, defaults={"action": action}, methods=["POST"])
