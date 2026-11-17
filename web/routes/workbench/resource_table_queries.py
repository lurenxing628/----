"""Read-only JSON table queries, with independent list and facet snapshots."""

from flask import current_app, g

from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_material_query import MaterialPageRequest
from core.models.workbench_resource_query import ResourcePageRequest
from core.models.workbench_resource_table_query import TABLE_KINDS, toolbar_scope, validate_facet_request
from core.services.workbench.material.queries import WorkbenchMaterialQueryService
from core.services.workbench.resource.queries import WorkbenchResourceQueryService
from core.shared.key_sets import keys_conform
from web.api_responses import query_success

from .api_responses import worded_read_endpoint
from .materials import material_entity
from .read_context import bind_read_snapshot, read_snapshot_time, rebind_read_snapshot
from .request_json import BodyTexts, read_json_body
from .resources import resource_entity
from .write_context import issue_write_context

MAX_TABLE_BODY_BYTES = 32 * 1024 * 1024
_SCOPE_FIELDS = {"query", "status", "category", "page", "size", "sort", "direction", "snapshot_ref", "column_filters"}
_BODY = BodyTexts(transport="查询条件格式不正确，当前列表没有变化。请刷新页面后重新选择。",
                  malformed="查询条件读不出来，当前列表没有变化。请点「清除筛选」后重新选择。",
                  incomplete="查询条件不完整，当前列表没有变化。请刷新页面后重新选择。",
                  duplicate="查询条件里有重复项，当前列表没有变化。请刷新页面后重新选择。")
_LIMIT = (MAX_TABLE_BODY_BYTES, "一次提交的查询条件超过 32 MB，当前列表没有变化。请缩小筛选范围后重试。")


def _body():
    return read_json_body(_BODY, limit=_LIMIT)


def _scope(kind, value):
    if kind not in TABLE_KINDS:
        raise WorkbenchCommandRejected("entity_not_found", "这类记录的表头不支持筛选，当前列表没有变化。请改用上方的筛选条。", 404)
    if not keys_conform(value, (), _SCOPE_FIELDS):
        raise WorkbenchCommandRejected("invalid_input", "筛选范围里有不支持的列，当前列表没有变化。请刷新页面后重新选择。", 400)
    fields = dict(value)
    token = fields.pop("snapshot_ref", None)
    if "page" in fields:
        fields["number"] = fields.pop("page")
    if kind == "material":
        if fields.pop("category", None) is not None:
            raise WorkbenchCommandRejected("invalid_input", "物料列表没有自制或外协的分类，当前列表没有变化。请去掉这个条件后重试。", 400)
        query = MaterialPageRequest(**fields)
    else:
        query = ResourcePageRequest(kind, **fields)
    return query, token


def _reader(kind):
    return WorkbenchMaterialQueryService(g.db, current_app.logger) if kind == "material" else WorkbenchResourceQueryService(g.db, kind, current_app.logger)


_readonly_endpoint = worded_read_endpoint("列表没有读出来，数据没有任何改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。")


@_readonly_endpoint
def resource_table_query(kind):
    query, token = _scope(kind, _body())
    if query.number > 1 and token is None:
        raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
    if isinstance(query, MaterialPageRequest):
        return _material_table_query(query, token)
    return _resource_table_query(query, token)


def _material_table_query(query: MaterialPageRequest, token):
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchMaterialQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot(query.scope(), scope.state_fingerprint(), token, as_of=as_of, binding=binding)
        records, page = scope.page(query)
        if query.number > page["pages"]:
            raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
        entities = [material_entity(record) for record in records]
        metrics = scope.metrics(query)
        data = {"entities": entities, "page": page, "metrics": metrics,
                "create_context": issue_write_context("material:create", ["material.create"], None)}
        return query_success(data, snapshot)


def _resource_table_query(query: ResourcePageRequest, token):
    kind = query.kind
    as_of, binding = read_snapshot_time(token)
    reader = WorkbenchResourceQueryService(g.db, kind, current_app.logger)
    with reader.read_snapshot() as scope:
        snapshot = bind_read_snapshot(query.scope(), scope.state_fingerprint(), token, as_of=as_of, binding=binding)
        records, page = scope.page(query)
        if query.number > page["pages"]:
            raise WorkbenchCommandRejected("snapshot_stale", "翻页位置已失效，请回到第 1 页重新查询。")
        entities = [resource_entity(kind, record) for record in records]
        metrics = page.pop("metrics")
        data = {"entities": entities, "page": page, "metrics": metrics,
                "create_context": issue_write_context(kind + ":create", [kind + ".create"], reader.create_relations_snapshot())}
        return query_success(data, snapshot)


def _facet_query(kind, body, *, selection=False):
    if not keys_conform(body, ("scope", "column"), ("query", "size", "snapshot_ref") + (() if selection else ("page",))):
        raise WorkbenchCommandRejected("invalid_input", "列筛选的条件不对，筛选没有变化。请刷新页面后重新打开列筛选。", 400)
    query, list_token = _scope(kind, body["scope"])
    column, search = body["column"], body.get("query", "")
    number, size = body.get("page", 1), body.get("size", 100)
    validate_facet_request(query, column, search, number, size)
    facet_token = body.get("snapshot_ref")
    if (selection or number > 1) and facet_token is None:
        raise WorkbenchCommandRejected("snapshot_stale", "列筛选的可选值已过期，筛选没有变化。请关掉后重新打开列筛选。")
    signature = {"kind": "resource_table_facets", "scope": toolbar_scope(query), "column": column, "query": search, "size": size}
    as_of, binding = read_snapshot_time(facet_token)
    reader = _reader(kind)
    with reader.read_snapshot() as scope:
        fingerprint = scope.state_fingerprint()
        if list_token is not None:
            rebind_read_snapshot(query.scope(), fingerprint, list_token)
        snapshot = bind_read_snapshot(signature, fingerprint, facet_token, as_of=as_of, binding=binding)
        data = scope.facet_selection(query, column, search) if selection else scope.facets(query, column, search, number, size)
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
