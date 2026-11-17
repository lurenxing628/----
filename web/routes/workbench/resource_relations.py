"""Explicit read-only relation endpoint; registration is owned by the integrator."""

import re

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.resource.relations import ResourceRelationRequest, WorkbenchResourceRelationService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .read_context import bind_read_snapshot, read_snapshot_time
from .request_json import single_value_arguments


def _relation_query():
    allowed = {"relation", "query", "page", "size", "snapshot_ref"}
    single_value_arguments(allowed, message="关联查询的条件有重复或不支持的项，当前列表没有变化。请刷新页面后重新选择。")
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码或每页条数填写不对，列表没有变化。请回到第 1 页重新查询。", 400)
        values[key] = int(text)
    query = ResourceRelationRequest(request.args.get("relation", ""), query=request.args.get("query", ""),
                                    number=values["page"], size=values["size"])
    if query.number > 1 and "snapshot_ref" not in request.args:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
    return query


@api_endpoint
def resource_relations(kind, ref):
    query = _relation_query()
    token = request.args.get("snapshot_ref")
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchResourceRelationService(g.db, current_app.logger)
    with reader.read_snapshot(
        kind,
        ref,
        query,
        bind_snapshot=lambda fingerprint: bind_read_snapshot(query.scope(ref), fingerprint, token, as_of=as_of,
                                                             binding=binding),
    ) as (snapshot, data):
        return query_success(data, snapshot)


def register_resource_relation_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/<ref>/relations", view_func=resource_relations, methods=["GET"])
