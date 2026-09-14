"""Process facets share the full process snapshot and retain other column rules."""

import json
import re

from flask import current_app, g, request

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_process_table_query import (
    process_facet_scope,
    process_table_request,
    unique_process_table_object,
    validate_process_facet_request,
)
from core.services.workbench import messages
from core.services.workbench.process_queries import WorkbenchProcessQueryService

from .api_responses import api_endpoint, query_success
from .read_context import bind_read_snapshot


def _positive(key, default):
    value = request.args.get(key, str(default))
    if re.fullmatch(r"[1-9][0-9]{0,6}", value) is None:
        raise WorkbenchCommandRejected("invalid_input", "页码或每页数量填写不对，筛选选项没有变化。请回到第 1 页重新查询。", 400)
    return int(value)


@api_endpoint
def process_facets(column, selection=False):
    allowed = {"scope", "query", "page", "size", "snapshot_ref"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "列筛选的查询条件有重复或不支持的项，筛选没有变化。请刷新页面后重新打开列筛选。", 400)
    try:
        scope = json.loads(request.args.get("scope", "{}"), object_pairs_hook=unique_process_table_object)
    except (ValueError, TypeError) as exc:
        raise WorkbenchCommandRejected("invalid_input", "筛选内容读不出来，筛选没有变化。请点「清除筛选」后重新选择。", 400) from exc
    query = process_table_request(scope)
    search, number, size = request.args.get("query", ""), _positive("page", 1), _positive("size", 100)
    validate_process_facet_request(column, search, number, size)
    if selection and number != 1:
        raise WorkbenchCommandRejected("invalid_input", "「全选当前筛选」不分页，这次没有翻页。请直接点「全选当前筛选」。", 400)
    token = request.args.get("snapshot_ref")
    if (selection or number > 1) and not token:
        raise WorkbenchCommandRejected("snapshot_stale", messages.STALE)
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(process_facet_scope(query, column, search, size), state, token)
        table = reader.table()
        data = table.facet_selection(query, column, search, size) if selection else table.facets(query, column, search, number, size)
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


def register_process_table_routes(bp):
    bp.add_url_rule("/api/workbench/v1/process-table/facets/<column>", view_func=process_facets, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/process-table/facet-selection/<column>", endpoint="process_facet_selection",
                    view_func=process_facets, defaults={"selection": True}, methods=["GET"])
