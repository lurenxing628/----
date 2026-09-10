"""Read-only JSON table queries, with independent list and facet snapshots."""

import json
from functools import wraps

from flask import current_app, g, request
from werkzeug.exceptions import HTTPException

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_query import ResourcePageRequest
from core.models.workbench_resource_table_query import TABLE_KINDS, toolbar_scope, validate_facet_request
from core.services.workbench.material_queries import WorkbenchMaterialQueryService
from core.services.workbench.materials import WorkbenchMaterialService
from core.services.workbench.resource_queries import WorkbenchResourceQueryService

from .api_responses import api_endpoint, query_success
from .materials import _entity_with_context
from .read_context import bind_read_snapshot
from .resources import _with_context
from .write_context import issue_write_context

MAX_TABLE_BODY_BYTES = 32 * 1024 * 1024
_SCOPE_FIELDS = {"query", "status", "category", "page", "size", "sort", "direction", "snapshot_ref", "column_filters"}


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WorkbenchCommandRejected("invalid_input", "查询JSON包含重复字段。", 400)
        result[key] = value
    return result


def _body():
    if request.args or not request.is_json:
        raise WorkbenchCommandRejected("invalid_input", "表格查询必须使用JSON正文，不能带URL查询参数。", 400)
    if request.content_length is not None and request.content_length > MAX_TABLE_BODY_BYTES:
        raise WorkbenchCommandRejected("capacity_exceeded", "查询正文超过32 MiB，请缩小筛选范围。", 413)
    raw = request.stream.read(MAX_TABLE_BODY_BYTES + 1)
    if len(raw) > MAX_TABLE_BODY_BYTES:
        raise WorkbenchCommandRejected("capacity_exceeded", "查询正文超过32 MiB，请缩小筛选范围。", 413)
    try:
        body = json.loads(raw, object_pairs_hook=_unique_object)
    except (ValueError, UnicodeError) as exc:
        if isinstance(exc, WorkbenchCommandRejected):
            raise
        raise WorkbenchCommandRejected("invalid_input", "查询正文不是有效JSON。", 400) from exc
    if type(body) is not dict:
        raise WorkbenchCommandRejected("invalid_input", "查询正文必须是对象。", 400)
    return body


def _scope(kind, value):
    if kind not in TABLE_KINDS:
        raise WorkbenchCommandRejected("entity_not_found", "此资源没有表头筛选入口。", 404)
    if type(value) is not dict or set(value) - _SCOPE_FIELDS:
        raise WorkbenchCommandRejected("invalid_input", "列表范围包含未知字段。", 400)
    fields = dict(value)
    token = fields.pop("snapshot_ref", None)
    if "page" in fields:
        fields["number"] = fields.pop("page")
    if kind == "material":
        if fields.pop("category", None) is not None:
            raise WorkbenchCommandRejected("invalid_input", "物料列表不支持工种归属。", 400)
        query = MaterialPageRequest(**fields)
    else:
        query = ResourcePageRequest(kind, **fields)
    return query, token


def _reader(kind):
    return WorkbenchMaterialQueryService(g.db, current_app.logger) if kind == "material" else WorkbenchResourceQueryService(g.db, kind, current_app.logger)


def _readonly_endpoint(function):
    @api_endpoint
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = function(*args, **kwargs)
            response.headers["Cache-Control"] = "no-store"
            return response
        except (WorkbenchCommandRejected, AppError, HTTPException):
            raise
        except Exception as exc:
            # POST is only a transport for large read scopes, never an uncertain write.
            raise WorkbenchCommandRejected("storage_failure", "表格读取失败，未写入任何业务结果。", 500) from exc
    return wrapped


@_readonly_endpoint
def resource_table_query(kind):
    query, token = _scope(kind, _body())
    if query.number > 1 and token is None:
        raise WorkbenchCommandRejected("snapshot_stale", "继续翻页需要原列表快照，请先刷新。")
    if isinstance(query, MaterialPageRequest):
        return _material_table_query(query, token)
    return _resource_table_query(query, token)


def _material_table_query(query: MaterialPageRequest, token):
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query.scope(), state, token)
        records, page = reader.page(query)
        if query.number > page["pages"]:
            raise WorkbenchCommandRejected("snapshot_stale", "列表页码已过时，请刷新。")
        domain = WorkbenchMaterialService(g.db, current_app.logger)
        entities = [_entity_with_context(record, domain) for record in records]
        metrics = reader.metrics(query)
        data = {"entities": entities, "page": page, "metrics": metrics,
                "create_context": issue_write_context("material:create", ["material.create"], state)}
        return query_success(data, snapshot)


def _resource_table_query(query: ResourcePageRequest, token):
    kind = query.kind
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query.scope(), state, token)
        records, page = reader.page(query)
        if query.number > page["pages"]:
            raise WorkbenchCommandRejected("snapshot_stale", "列表页码已过时，请刷新。")
        entities = [_with_context(kind, record) for record in records]
        metrics = page.pop("metrics")
        data = {"entities": entities, "page": page, "metrics": metrics,
                "create_context": issue_write_context(kind + ":create", [kind + ".create"], state)}
        return query_success(data, snapshot)


def _facet_query(kind, body, *, selection=False):
    allowed = {"scope", "column", "query", "size", "snapshot_ref"} | (set() if selection else {"page"})
    if set(body) - allowed or not {"scope", "column"}.issubset(body):
        raise WorkbenchCommandRejected("invalid_input", "筛选值查询字段不正确。", 400)
    query, list_token = _scope(kind, body["scope"])
    column, search = body["column"], body.get("query", "")
    number, size = body.get("page", 1), body.get("size", 100)
    validate_facet_request(query, column, search, number, size)
    facet_token = body.get("snapshot_ref")
    if (selection or number > 1) and facet_token is None:
        raise WorkbenchCommandRejected("snapshot_stale", "继续读取筛选值需要菜单自身快照，请重新打开菜单。")
    signature = {"kind": "resource_table_facets", "scope": toolbar_scope(query), "column": column, "query": search, "size": size}
    reader = _reader(kind)
    with reader.read_snapshot() as state:
        if list_token is not None:
            bind_read_snapshot(query.scope(), state, list_token)
        snapshot = bind_read_snapshot(signature, state, facet_token)
        data = reader.facet_selection(query, column, search, size) if selection else reader.facets(query, column, search, number, size)
        return query_success(data, snapshot)


@_readonly_endpoint
def resource_table_facets(kind):
    return _facet_query(kind, _body())


@_readonly_endpoint
def resource_table_facet_selection(kind):
    return _facet_query(kind, _body(), selection=True)


def register_resource_table_routes(bp):
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/query", view_func=resource_table_query, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/facets", view_func=resource_table_facets, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/entities/<kind>/facet-selection", view_func=resource_table_facet_selection, methods=["POST"])
