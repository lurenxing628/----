"""Live typed resource APIs; callers never supply arbitrary table/field names."""

import re

from flask import current_app, g, jsonify, request

from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_resource_query import ResourcePageRequest
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService

from .api_responses import api_endpoint, query_success
from .materials import _command_body
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def _query(kind):
    allowed = {"query", "status", "category", "page", "size", "sort", "direction", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "资源列表包含未知或重复参数。", 400)
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码和每页条数必须是正整数。", 400)
        values[key] = int(text)
    return ResourcePageRequest(kind=kind, query=request.args.get("query", ""), status=request.args.get("status") or None,
                               category=request.args.get("category") or None, number=values["page"], size=values["size"],
                               sort=request.args.get("sort", "business_code"), direction=request.args.get("direction", "asc"))


def _with_context(kind, record):
    entity = dict(record.entity)
    relations = entity["relationships"]
    referenced = any(relations.get("counts", {}).values()) or relations.get("machine_count", 0) or relations.get("operator_count", 0)
    actions = [kind + ".update"] + ([] if referenced else [kind + ".delete"])
    context = issue_write_context(record.identity.ref, actions, record.state)
    context["capabilities"][kind + ".delete"] = not bool(referenced)
    if referenced:
        context["blocked_reasons"] = [{"action": kind + ".delete", "code": "constraint_conflict", "message": "资源仍被其他记录引用，不能删除。"}]
    entity["write_context"] = context
    return entity


@api_endpoint
def resource_list(kind):
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    query = _query(kind)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query.scope(), state, request.args.get("snapshot_ref"))
        records, page = reader.page(query)
        metrics = page.pop("metrics")
        data = {"entities": [_with_context(kind, record) for record in records], "page": page, "metrics": metrics,
                "create_context": issue_write_context(kind + ":create", [kind + ".create"], state)}
    return query_success(data, snapshot)


@api_endpoint
def resource_detail(kind, ref):
    if set(request.args) - {"snapshot_ref"} or len(request.args.getlist("snapshot_ref")) > 1:
        raise WorkbenchCommandRejected("invalid_input", "资源详情参数不正确。", 400)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot({"kind": kind, "entity_ref": ref}, state, request.args.get("snapshot_ref"))
        entity = _with_context(kind, reader.detail(ref))
    return query_success(entity, snapshot)


@api_endpoint
def resource_command(kind, action, ref=None):
    if action not in ("create", "update", "delete") or (action == "create") != (ref is None):
        raise WorkbenchCommandRejected("invalid_input", "资源操作入口不正确。", 400)
    body = _command_body()
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    normalized = reader.domain.normalize_input(action, body["input"])
    subject = kind + ":create" if action == "create" else ref
    if not isinstance(subject, str) or not subject:
        raise WorkbenchCommandRejected("invalid_input", "资源操作缺少对象引用。", 400)
    command = kind + "." + action

    def guard():
        identity = None if action == "create" else reader.resolve(ref)
        state = reader.state_fingerprint() if identity is None else reader.domain.snapshot(identity)
        validate_write_context(body["write_token"], subject, command, state)
        return identity

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action=command, context_ref=subject, normalized_input=normalized,
        guard=guard, mutate=lambda identity: reader.domain.apply(action, normalized, identity))
    return jsonify(outcome)


@api_endpoint
def resource_summary():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "资源统计入口不接受其他参数。", 400)
    reader = WorkbenchResourceQueryService(g.db, "op_type", current_app.logger)
    with reader.read_snapshot() as state:
        data = reader.summary_projection()
        snapshot = bind_read_snapshot({"kind": "resource_summary"}, input_fingerprint({"resources": state, "summary": data}))
    return query_success(data, snapshot)


def register_resource_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/<kind>", view_func=resource_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/<ref>", view_func=resource_detail, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/create", endpoint="resource_create", view_func=resource_command,
                    defaults={"action": "create"}, methods=["POST"])
    for action in ("update", "delete"):
        bp.add_url_rule("/api/workbench/v1/entities/<kind>/<ref>/" + action, endpoint="resource_" + action,
                        view_func=resource_command, defaults={"action": action}, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/resources/summary", view_func=resource_summary, methods=["GET"])
