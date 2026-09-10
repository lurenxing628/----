"""First entity API; other resource pages remain unconnected until their contracts land."""

from __future__ import annotations

import re

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_material_query import MaterialPageRequest
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.material_queries import WorkbenchMaterialQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context

_COLLECTION = "material:create"


def _services():
    from core.services.workbench.materials import WorkbenchMaterialService

    logger = current_app.logger
    return WorkbenchMaterialQueryService(g.db, logger), WorkbenchMaterialService(g.db, logger)


def _page_request():
    allowed = {"query", "status", "page", "size", "sort", "direction", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "列表包含不支持或重复的筛选参数。", 400)
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码和每页条数必须是正整数。", 400)
        values[key] = int(text)
    return MaterialPageRequest(query=request.args.get("query", ""), status=request.args.get("status") or None,
                               number=values["page"], size=values["size"], sort=request.args.get("sort", "business_code"),
                               direction=request.args.get("direction", "asc"))


def _entity_with_context(record, domain):
    entity = dict(record.entity)
    snapshot = domain.snapshot(record.identity)
    actions = ["material.update"]
    blocked = []
    if entity["relationships"]["batch_requirement_count"] == 0:
        actions.append("material.delete")
    else:
        blocked.append({"action": "material.delete", "code": "constraint_conflict", "message": "物料已被批次需求引用，不能删除。"})
    context = issue_write_context(record.identity.ref, actions, snapshot)
    context["capabilities"]["material.delete"] = "material.delete" in actions
    context["blocked_reasons"] = blocked
    entity["write_context"] = context
    return entity


@api_endpoint
def material_list():
    scope = _page_request()
    reader, domain = _services()
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(scope.scope(), fingerprint, request.args.get("snapshot_ref"))
        records, page = reader.page(scope)
        data = {"entities": [_entity_with_context(record, domain) for record in records], "page": page, "metrics": reader.metrics(scope),
                "create_context": issue_write_context(_COLLECTION, ["material.create"], fingerprint)}
    return query_success(data, snapshot)


@api_endpoint
def material_detail(ref):
    if set(request.args) - {"snapshot_ref"} or len(request.args.getlist("snapshot_ref")) > 1:
        raise WorkbenchCommandRejected("invalid_input", "详情查询参数不正确。", 400)
    reader, domain = _services()
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot({"kind": "material", "entity_ref": ref}, fingerprint, request.args.get("snapshot_ref"))
        entity = _entity_with_context(reader.detail(ref), domain)
    return query_success(entity, snapshot)


def _command_body():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "保存请求必须使用约定的JSON内容，不能带查询参数。", 400)
    body = request.get_json()
    if not isinstance(body, dict) or set(body) != {"request_key", "write_token", "input"}:
        raise WorkbenchCommandRejected("invalid_input", "保存请求缺少必要字段或包含未知字段。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if not isinstance(body["write_token"], str) or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "保存所需资料不完整，请重新读取最新资料。", 400)
    return body


@api_endpoint
def material_command(action, ref=None):
    if action not in ("create", "update", "delete") or (action == "create") != (ref is None):
        raise WorkbenchCommandRejected("invalid_input", "物料操作入口不正确。", 400)
    body = _command_body()
    reader, domain = _services()
    normalized = domain.normalize_input(action, body["input"])
    subject = _COLLECTION if action == "create" else ref
    if not isinstance(subject, str) or not subject:
        raise WorkbenchCommandRejected("invalid_input", "物料操作缺少对象引用。", 400)
    command = "material." + action

    def guard():
        identity = None if action == "create" else reader.resolve(ref)
        state = reader.state_fingerprint() if identity is None else domain.snapshot(identity)
        validate_write_context(body["write_token"], subject, command, state)
        return identity

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=command, context_ref=subject, normalized_input=normalized,
        guard=guard, mutate=lambda identity: domain.apply(action, normalized, identity))
    return jsonify(outcome)


@api_endpoint
def command_receipt(request_key):
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "回执查询不接受其他筛选参数。", 400)
    receipt = WorkbenchCommandService(g.db, current_app.logger).lookup(request_key)
    if receipt is not None:
        return jsonify(receipt)
    return jsonify({"ok": True, "state": "not_recorded", "receipt": None, "may_be_in_flight": True,
                    "message": "尚未查到已提交回执；原请求仍可能执行中，不要换一个请求重复提交。"})


def register_material_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/material", view_func=material_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/material/<ref>", view_func=material_detail, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/material/create", endpoint="material_create",
                    view_func=material_command, defaults={"action": "create"}, methods=["POST"])
    for action in ("update", "delete"):
        bp.add_url_rule("/api/workbench/v1/entities/material/<ref>/" + action, endpoint="material_" + action,
                        view_func=material_command, defaults={"action": action}, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/commands/<request_key>", view_func=command_receipt, methods=["GET"])
