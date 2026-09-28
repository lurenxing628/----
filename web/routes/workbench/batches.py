"""Independent batch route registration. Global mounting belongs to the host."""

from flask import current_app, g, jsonify, request

from core.models.workbench_batch import normalize_operation_input, object_fields, public_ref
from core.models.workbench_batch_material import normalize_material_changes
from core.models.workbench_batch_query import batch_scope, snapshot_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.bulk import WorkbenchBatchBulkService, normalize_bulk
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.operations import WorkbenchBatchOperationService
from core.services.workbench.batch.quantity_split import WorkbenchQuantitySplitService, normalize_split
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.batch.service import WorkbenchBatchService
from core.services.workbench.commands import WorkbenchCommandService
from web.api_responses import query_success

from .api_responses import api_endpoint
from .batch_context import command_body, json_body, load_preview, read_scope, save_preview
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context

COLLECTION = "batch:create"


def entity_context(entity, fingerprint):
    actions = ["batch.update", "batch.materials_update"]
    blocked = []
    if not entity["protected"]:
        actions.extend(("batch.sync_confirm", "batch.operation_update"))
        if entity["relationships"].get("quantity_split_reference_count", 0):
            blocked.append({"action": "batch.delete", "message": "这个批次有数量拆分记录，需保留原批与子批以核对数量，不能删除。"})
        elif not entity["relationships"]["material_requirement_count"]:
            actions.append("batch.delete")
        else:
            blocked.append({"action": "batch.delete", "message": "批次还挂着物料需求，不能删除。请先清除这个批次的物料需求，再删除批次。"})
    else:
        reason = ("已有外协发出或回厂登记，不能删除、重建或编辑工序，以免原登记无法继续核对回厂。"
                  if entity["relationships"].get("outsourcing_reference_count", 0)
                  else "已有排产、报工或执行状态记录，暂不能删除、替换或编辑工序。")
        for action in ("delete", "sync_confirm", "operation_update"):
            blocked.append({"action": "batch." + action, "message": reason})
    template = entity.get("template")
    if not entity["protected"] and template is not None and not template["complete"]:
        actions.remove("batch.sync_confirm")
        blocked.append({"action": "batch.sync_confirm", "message": "；".join(row["message"].rstrip("。") for row in template["diagnostics"]) + "。"})
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
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，还没有全选。请点「刷新」后重新点「全选当前筛选」。", 400)
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
    args = request.args
    if set(args) - {"batch_ref", "operation_ref"} or any(len(args.getlist(key)) != 1 for key in args) or bool(args.get("batch_ref")) != bool(args.get("operation_ref")):
        raise WorkbenchCommandRejected("invalid_input", "请选择完整的批次及工序后再读取候选资源。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        data = reader.choices(args.get("batch_ref"), args.get("operation_ref"))
        snapshot = bind_read_snapshot({"kind": "batch_choices", **dict(args)}, fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_command(action, ref=None):
    body = command_body()
    domain = WorkbenchBatchService(g.db, current_app.logger)
    if action == "materials_update":
        normalized = normalize_material_changes(body["input"])
    else:
        normalized = normalize_operation_input(body["input"]) if action == "operation_update" else domain.normalize(action, body["input"])
    subject = COLLECTION if action == "create" else public_ref(ref)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)

    def guard():
        if ref is not None:
            reader.resolve(ref)
        validate_write_context(body["write_token"], subject, "batch." + action, reader.fingerprint())

    def mutate(_checked):
        if action == "materials_update":
            return WorkbenchBatchMaterialService(g.db, current_app.logger).apply(ref, normalized)
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
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，还没有保存。请刷新页面后重新点「预览变更」。", 400)
    payload = (normalize_bulk(body["input"]) if action == "bulk_confirm" else
               normalize_split(body["input"]) if action == "split_confirm" else
               WorkbenchBatchOperationService.normalize_sync(body["input"]))
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        if action in ("sync_confirm", "split_confirm"):
            bind_read_snapshot({"kind": "batch", "ref": ref}, fingerprint, body["snapshot_ref"])
            if action == "split_confirm":
                data = WorkbenchQuantitySplitService(g.db, current_app.logger).plan(ref, payload)
                data["materials"] = [{"business_code": row["material_id"], **{key: value for key, value in row.items()
                                     if key not in ("requirement_id", "operation_id", "material_id")}} for row in data["materials"]]
            else:
                data = WorkbenchBatchOperationService(g.db, current_app.logger).sync_preview(ref, payload)
        else:
            scope = batch_scope(body["scope"])
            bind_read_snapshot(snapshot_scope(scope), fingerprint, body["snapshot_ref"])
            data = WorkbenchBatchBulkService(g.db, current_app.logger).plan(payload)
            if not isinstance(body["snapshot_ref"], str) or not body["snapshot_ref"]:
                raise WorkbenchCommandRejected("invalid_input", "数据已更新，批量修改还没有保存。请刷新页面后重新点「预览变更」。", 400)
        preview = save_preview(action, ref, payload, fingerprint)
        data.update(preview_ref=preview, write_context=issue_write_context(ref or preview, ["batch." + action],
                    {"fingerprint": fingerprint, "input": payload}), warnings=data.get("warnings", []))
        snapshot = bind_read_snapshot({"kind": "batch_preview", "preview_ref": preview}, fingerprint)
    return query_success(data, snapshot)


@api_endpoint
def batch_facets():
    from core.models.workbench_batch import SORTS
    from core.services.workbench.batch.queries import cell

    body = object_fields(json_body(), ("scope", "field"), ("scope", "field"))
    scope = batch_scope(body["scope"])
    if body["field"] not in SORTS or not scope.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "要筛选的列不对或数据已更新，筛选没有变化。请点「刷新」后重新打开列筛选。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as fingerprint:
        snapshot = bind_read_snapshot(snapshot_scope(scope), fingerprint, scope["snapshot_ref"])
        filters = {key: values for key, values in scope["column_filters"].items() if key != body["field"]}
        rows = reader.matched({**scope, "column_filters": filters})
        values = list(dict.fromkeys(cell(row, body["field"]) for row in rows))
        values.sort(key=lambda value: (value is None, str(value)))
        if len(values) > 5000:
            raise WorkbenchCommandRejected("invalid_input", "这一列的可选值超过 5000 项，没有全部列出。请在搜索框里先输入关键字缩小范围。", 422)
    return query_success({"field": body["field"], "values": values, "count": len(values)}, snapshot)


@api_endpoint
def batch_confirm(action, ref=None):
    body = command_body()
    normalized = dict(object_fields(body["input"], ("preview_ref",), ("preview_ref",)))
    token = normalized["preview_ref"]
    if not isinstance(token, str) or not token:
        raise WorkbenchCommandRejected("invalid_input", "预检结果编号缺失，还没有保存。请重新点「预览变更」。", 400)

    def guard():
        binding = load_preview(token, action, ref)
        fingerprint = WorkbenchBatchQueryService(g.db, current_app.logger).fingerprint()
        if binding["fingerprint"] != fingerprint:
            raise WorkbenchCommandRejected("stale_write", "预检之后资料有变化，还没有保存。请重新点「预览变更」。")
        validate_write_context(body["write_token"], ref or token, "batch." + action, {"fingerprint": fingerprint, "input": binding["input"]})
        return binding["input"]

    def mutate(payload):
        if action == "split_confirm":
            return WorkbenchQuantitySplitService(g.db, current_app.logger).apply(ref, payload)
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
    for action in ("update", "delete", "operation_update", "materials_update"):
        bp.add_url_rule(base + "/<ref>/" + action, endpoint="batch_" + action, view_func=batch_command, defaults={"action": action}, methods=["POST"])
    for name, path in (("bulk", ""), ("sync", "/<ref>"), ("split", "/<ref>")):
        for suffix, func in (("preview", batch_preview), ("confirm", batch_confirm)):
            bp.add_url_rule(base + path + "/" + name + "-" + suffix, endpoint="batch_" + name + "_" + suffix,
                            view_func=func, defaults={"action": name + "_confirm"}, methods=["POST"])
    register_batch_file_routes(bp)
