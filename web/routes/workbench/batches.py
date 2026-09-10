"""Independent batch route registration. Global mounting belongs to the host."""

from flask import current_app, g, jsonify, request

from core.models.workbench_batch import normalize_operation_input, object_fields, public_ref
from core.models.workbench_batch_query import batch_scope, snapshot_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch_bulk import WorkbenchBatchBulkService, normalize_bulk
from core.services.workbench.batch_operations import WorkbenchBatchOperationService
from core.services.workbench.batch_queries import WorkbenchBatchQueryService
from core.services.workbench.batches import WorkbenchBatchService
from core.services.workbench.commands import WorkbenchCommandService

from .api_responses import api_endpoint, query_success
from .batch_context import command_body, json_body, load_preview, read_scope, save_preview
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context

COLLECTION = "batch:create"


def entity_context(entity, fingerprint):
    actions = ["batch.update"]
    blocked = []
    if not entity["protected"]:
        actions.extend(("batch.sync_confirm", "batch.operation_update"))
        if not entity["relationships"]["material_requirement_count"]:
            actions.append("batch.delete")
        else:
            blocked.append({"action": "batch.delete", "message": "批次仍有物料需求，不能直接删除。"})
    else:
        blocked.append({"action": "batch.delete", "message": "批次已有计划或执行事实，不能删除或重建工序。"})
    context = issue_write_context(entity["ref"], actions, fingerprint)
    for action in ("delete", "sync_confirm", "operation_update"):
        context["capabilities"]["batch." + action] = "batch." + action in actions
    context["blocked_reasons"] = blocked
    entity["write_context"] = context
    return entity


def _list(scope):
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(snapshot_scope(scope), fingerprint, scope.get("snapshot_ref"))
        data = reader.page(scope)
        data["entities"] = [entity_context(entity, fingerprint) for entity in data["entities"]]
        data["create_context"] = issue_write_context(COLLECTION, ["batch.create"], fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_list():
    return _list(read_scope())


@api_endpoint
def batch_query():
    return _list(batch_scope(json_body()))


@api_endpoint
def batch_selection():
    scope = batch_scope(json_body())
    if not scope.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "全选需要当前列表快照。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(snapshot_scope(scope), fingerprint, scope["snapshot_ref"])
        data = reader.selection(scope)
    return query_success(data, snapshot)


@api_endpoint
def batch_detail(ref):
    object_fields(dict(request.args), ("snapshot_ref",))
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot({"kind": "batch", "ref": ref}, fingerprint, request.args.get("snapshot_ref"))
        data = entity_context(reader.detail(ref), fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_choices():
    if request.args:
        raise WorkbenchCommandRejected("invalid_input", "目录读取不接受其他参数。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        data = reader.choices()
        snapshot = bind_read_snapshot({"kind": "batch_choices"}, fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_command(action, ref=None):
    body = command_body()
    domain = WorkbenchBatchService(g.db, current_app.logger)
    normalized = normalize_operation_input(body["input"]) if action == "operation_update" else domain.normalize(action, body["input"])
    subject = COLLECTION if action == "create" else public_ref(ref)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)

    def guard():
        if ref is not None:
            reader.resolve(ref)
        validate_write_context(body["write_token"], subject, "batch." + action, reader.fingerprint())

    def mutate(_checked):
        if action == "operation_update":
            return WorkbenchBatchOperationService(g.db, current_app.logger).update(ref, normalized)
        return domain.apply(action, normalized, ref)

    return jsonify(WorkbenchCommandService(g.db, current_app.logger).execute(request_key=body["request_key"],
        action="batch." + action, context_ref=subject, normalized_input=normalized, guard=guard, mutate=mutate))


@api_endpoint
def batch_preview(action, ref=None):
    body = json_body()
    required = ("input", "snapshot_ref", "scope") if action == "bulk_confirm" else ("input", "snapshot_ref")
    object_fields(body, required, required)
    if not isinstance(body["snapshot_ref"], str) or not body["snapshot_ref"]:
        raise WorkbenchCommandRejected("invalid_input", "预览缺少当前资料快照。", 400)
    payload = normalize_bulk(body["input"]) if action == "bulk_confirm" else WorkbenchBatchOperationService.normalize_sync(body["input"])
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        if action == "sync_confirm":
            bind_read_snapshot({"kind": "batch", "ref": ref}, fingerprint, body["snapshot_ref"])
            data = WorkbenchBatchOperationService(g.db, current_app.logger).sync_preview(ref, payload)
        else:
            scope = batch_scope(body["scope"])
            bind_read_snapshot(snapshot_scope(scope), fingerprint, body["snapshot_ref"])
            data = WorkbenchBatchBulkService(g.db, current_app.logger).plan(payload)
            if not isinstance(body["snapshot_ref"], str) or not body["snapshot_ref"]:
                raise WorkbenchCommandRejected("invalid_input", "批量预览缺少列表快照。", 400)
        preview = save_preview(action, ref, payload, fingerprint)
        data.update(preview_ref=preview, write_context=issue_write_context(ref or preview, ["batch." + action],
                    {"fingerprint": fingerprint, "input": payload}), warnings=data.get("warnings", []))
        snapshot = bind_read_snapshot({"kind": "batch_preview", "preview_ref": preview}, fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_facets():
    from core.models.workbench_batch import SORTS
    from core.services.workbench.batch_queries import cell

    body = object_fields(json_body(), ("scope", "field"), ("scope", "field"))
    scope = batch_scope(body["scope"])
    if body["field"] not in SORTS or not scope.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "列筛选缺少有效字段或当前快照。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(snapshot_scope(scope), fingerprint, scope["snapshot_ref"])
        filters = {key: values for key, values in scope["column_filters"].items() if key != body["field"]}
        rows = reader.matched({**scope, "column_filters": filters})
        values = list(dict.fromkeys(cell(row, body["field"]) for row in rows))
        values.sort(key=lambda value: (value is None, str(value)))
        if len(values) > 5000:
            raise WorkbenchCommandRejected("invalid_input", "列值超过5000项，请缩小搜索范围。", 422)
    return query_success({"field": body["field"], "values": values, "count": len(values)}, snapshot)


@api_endpoint
def batch_confirm(action, ref=None):
    body = command_body()
    normalized = dict(object_fields(body["input"], ("preview_ref",), ("preview_ref",)))
    token = normalized["preview_ref"]
    if not isinstance(token, str) or not token:
        raise WorkbenchCommandRejected("invalid_input", "确认缺少预览引用。", 400)

    def guard():
        binding = load_preview(token, action, ref)
        fingerprint = WorkbenchBatchQueryService(g.db, current_app.logger).fingerprint()
        if binding["fingerprint"] != fingerprint:
            raise WorkbenchCommandRejected("stale_write", "预览后资料发生变化，请重新预览。")
        validate_write_context(body["write_token"], ref or token, "batch." + action, {"fingerprint": fingerprint, "input": binding["input"]})
        return binding["input"]

    def mutate(payload):
        if action == "bulk_confirm":
            return WorkbenchBatchBulkService(g.db, current_app.logger).apply(payload)
        return WorkbenchBatchOperationService(g.db, current_app.logger).sync(ref, payload)

    return jsonify(WorkbenchCommandService(g.db, current_app.logger).execute(request_key=body["request_key"], action="batch." + action,
        context_ref=ref or token, normalized_input=normalized, guard=guard, mutate=mutate))


def register_batch_routes(bp):
    from .batch_files import register_batch_file_routes

    base = "/api/workbench/v1/entities/batch"
    for path, endpoint, method in (("", batch_list, "GET"), ("/query", batch_query, "POST"), ("/selection", batch_selection, "POST"), ("/facets", batch_facets, "POST"),
                                   ("/choices", batch_choices, "GET"), ("/<ref>", batch_detail, "GET")):
        bp.add_url_rule(base + path, view_func=endpoint, methods=[method])
    bp.add_url_rule(base + "/create", endpoint="batch_create", view_func=batch_command, defaults={"action": "create"}, methods=["POST"])
    for action in ("update", "delete", "operation_update"):
        bp.add_url_rule(base + "/<ref>/" + action, endpoint="batch_" + action, view_func=batch_command, defaults={"action": action}, methods=["POST"])
    for name, path in (("bulk", ""), ("sync", "/<ref>")):
        for suffix, func in (("preview", batch_preview), ("confirm", batch_confirm)):
            bp.add_url_rule(base + path + "/" + name + "-" + suffix, endpoint="batch_" + name + "_" + suffix,
                            view_func=func, defaults={"action": name + "_confirm"}, methods=["POST"])
    register_batch_file_routes(bp)
