"""Explicit read-only relation endpoint; registration is owned by the integrator."""

import re

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.resource_relations import ResourceRelationRequest, WorkbenchResourceRelationService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


def _relation_query():
    allowed = {"relation", "query", "page", "size", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "关联查询包含未知或重复参数。", 400)
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码和每页条数必须是正整数。", 400)
        values[key] = int(text)
    query = ResourceRelationRequest(request.args.get("relation", ""), query=request.args.get("query", ""),
                                    number=values["page"], size=values["size"])
    if query.number > 1 and "snapshot_ref" not in request.args:
        raise WorkbenchCommandRejected("snapshot_stale", "继续翻页需要原读取快照，请从第一页明确刷新。")
    return query


@api_endpoint
def resource_relations(kind, ref):
    query = _relation_query()
    reader = WorkbenchResourceRelationService(g.db, current_app.logger)
    with reader.read_snapshot(kind, ref, query) as (fingerprint, data):
        snapshot = bind_read_snapshot(query.scope(ref), fingerprint, request.args.get("snapshot_ref"))
        response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_resource_relation_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/<ref>/relations", view_func=resource_relations, methods=["GET"])
