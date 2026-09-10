"""Process read/preview endpoints; no stage mutation or legacy form dispatch."""

import json
import re

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint
from core.models.workbench_process_query import ProcessPageRequest
from core.models.workbench_process_table_query import ProcessTablePageRequest, unique_process_table_object
from core.services.workbench.process_projection import capabilities
from core.services.workbench.process_queries import WorkbenchProcessQueryService
from core.services.workbench.process_route_preview import ProcessRoutePreviewService

from .api_responses import api_endpoint, query_success
from .process_json import read_process_json
from .read_context import bind_read_snapshot
from .write_context import issue_write_context


def _list_query():
    allowed = {"query", "stage", "page", "size", "sort", "direction", "snapshot_ref", "column_filters"}
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise WorkbenchCommandRejected("invalid_input", "工艺列表包含未知或重复参数。", 400)
    values = {}
    for key, default in (("page", "1"), ("size", "20")):
        text = request.args.get(key, default)
        if re.fullmatch(r"[1-9][0-9]{0,6}", text) is None:
            raise WorkbenchCommandRejected("invalid_input", "页码和每页条数必须是正整数。", 400)
        values[key] = int(text)
    ordering = request.args.get("sort", "business_code")
    if "column_filters" in request.args or ordering.lstrip().startswith("["):
        try:
            sort = json.loads(ordering, object_pairs_hook=unique_process_table_object) if ordering.lstrip().startswith("[") else ordering
            filters = json.loads(request.args.get("column_filters", "{}"), object_pairs_hook=unique_process_table_object)
        except (ValueError, TypeError) as exc:
            raise WorkbenchCommandRejected("invalid_input", "工艺排序或筛选内容无法读取，请重新选择。", 400) from exc
        return ProcessTablePageRequest(query=request.args.get("query", ""), stage=request.args.get("stage") or None,
                                       number=values["page"], size=values["size"], sort=sort,
                                       direction=request.args.get("direction", "asc"), column_filters=filters)
    return ProcessPageRequest(query=request.args.get("query", ""), stage=request.args.get("stage") or None,
                              number=values["page"], size=values["size"], sort=request.args.get("sort", "business_code"),
                              direction=request.args.get("direction", "asc"))


def _response(data, snapshot):
    response = query_success(data, snapshot)
    response.headers["Cache-Control"] = "no-store"
    return response


@api_endpoint
def process_list():
    query = _list_query()
    token = request.args.get("snapshot_ref")
    if query.number > 1 and token is None:
        raise WorkbenchCommandRejected("snapshot_stale", "继续翻页需要原列表快照，请先刷新。")
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query.scope(), state, token)
        data = reader.table().page(query) if isinstance(query, ProcessTablePageRequest) else reader.page(query)
        data["capabilities"] = capabilities()
        data["create_context"] = issue_write_context("process:create", ["process.create"], state)
        if query.number > data["page"]["pages"]:
            raise WorkbenchCommandRejected("snapshot_stale", "工艺列表页码已过时，请刷新。")
    return _response(data, snapshot)


@api_endpoint
def process_detail(ref):
    if set(request.args) - {"snapshot_ref"} or len(request.args.getlist("snapshot_ref")) > 1:
        raise WorkbenchCommandRejected("invalid_input", "工艺详情参数不正确。", 400)
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        data = reader.detail(ref)
        snapshot = bind_read_snapshot({"kind": "part", "entity_ref": ref}, state, request.args.get("snapshot_ref"))
        if data["workflow"]["source"]["state"] == "confirmed":
            data["write_context"] = issue_write_context(ref, ["process.hours_confirm"], state)
    return _response(data, snapshot)


def _body():
    return read_process_json("路线预检", 1024 * 1024)


@api_endpoint
def process_route_preview(ref):
    from core.services.workbench.process_mutations import WorkbenchProcessMutationService

    try:
        body = _body()
        token = body.pop("snapshot_ref", None)
        if body.get("mode") == "rows" and isinstance(body.get("rows"), list) and any(
                isinstance(row, dict) and type(row.get("seq")) is int and abs(row["seq"]) > (1 << 53) - 1 for row in body["rows"]):
            raise WorkbenchCommandRejected("invalid_input", "逐行工序号超出浏览器可精确输入范围，请使用路线文字预览；未四舍五入序号。", 422)
        reader = WorkbenchProcessQueryService(g.db, current_app.logger)
        with reader.read_snapshot() as state:
            reader.resolve(ref)
            if token is not None:
                bind_read_snapshot({"kind": "part", "entity_ref": ref}, state, token)
            preview = ProcessRoutePreviewService(g.db, current_app.logger).preview(body)
            data = reader.route_difference(ref, preview)
            data["affected_groups"] = []
            if data["can_confirm_route"]:
                domain = WorkbenchProcessMutationService(g.db, current_app.logger)
                normalized = domain.normalize("route_confirm", {"route": body, "discard_group_refs": []})
                affected = set(domain.affected_groups("route_confirm", normalized, reader.resolve(ref)))
                data["affected_groups"] = [row for row in reader.detail(ref)["external_groups"] if row["ref"] in affected]
                data["write_context"] = issue_write_context(ref, ["process.route_confirm"], {"state": state, "input": normalized["route"]})
            snapshot = bind_read_snapshot({"kind": "process_route_preview", "entity_ref": ref,
                                           "input_hash": input_fingerprint(body)}, state)
        return _response(data, snapshot)
    except (WorkbenchCommandRejected, AppError, HTTPException):
        raise
    except Exception as exc:
        raise WorkbenchCommandRejected("storage_failure", "工艺预检读取失败，未保存路线或修改模板。", 500) from exc


def register_process_read_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/part", view_func=process_list, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/entities/part/<ref>", view_func=process_detail, methods=["GET"])
    bp.add_url_rule("/api/workbench/v1/process/<ref>/route-preview", view_func=process_route_preview, methods=["POST"])
