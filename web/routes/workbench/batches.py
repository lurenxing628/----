"""Independent batch route registration. Global mounting belongs to the host."""

from flask import current_app, g, request

from core.models.workbench_batch import normalize_batch_input, normalize_operation_input, object_fields, public_ref
from core.models.workbench_batch_material import normalize_material_changes
from core.models.workbench_batch_query import batch_scope, snapshot_scope
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.workbench.batch.bulk import WorkbenchBatchBulkService, normalize_bulk
from core.services.workbench.batch.materials import WorkbenchBatchMaterialService
from core.services.workbench.batch.operations import WorkbenchBatchOperationService
from core.services.workbench.batch.projection import batch_action_policy
from core.services.workbench.batch.quantity_split import WorkbenchQuantitySplitService, normalize_split
from core.services.workbench.batch.queries import WorkbenchBatchQueryService
from core.services.workbench.batch.scope import BatchFactScope
from core.services.workbench.batch.service import WorkbenchBatchService
from core.services.workbench.commands import WorkbenchCommandService
from web.api_responses import json_response, query_success

from .api_responses import api_endpoint, read_endpoint
from .batch_context import BODY, STALE, load_preview, read_scope, retry_hint, retry_message, save_preview
from .batch_files import register_batch_file_routes
from .read_context import bind_read_snapshot, current_snapshot_time
from .request_json import command_body, read_json_body, single_value_arguments
from .write_context import (
    issue_write_context,
    preview_write_context,
    validate_preview_confirmation,
    validate_write_context,
)

COLLECTION = "batch:create"


def entity_context(entity, issue_context):
    actions, capabilities, blocked = batch_action_policy(entity)
    context = issue_context(entity["ref"], actions)
    context["capabilities"].update(capabilities)
    context["blocked_reasons"] = blocked
    entity["write_context"] = context
    return entity


def _list(query):
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    snapshot = None

    def bind(fingerprint):
        nonlocal snapshot
        snapshot = bind_read_snapshot(snapshot_scope(query), fingerprint, query.get("snapshot_ref"), as_of=reader.as_of)

    data, fingerprint = reader.read_page(query, bind=bind)
    issue_context = issue_write_context.for_snapshot(fingerprint)
    data["entities"] = [entity_context(entity, issue_context) for entity in data["entities"]]
    data["create_context"] = issue_context(COLLECTION, ["batch.create"])
    return query_success(data, snapshot)


@api_endpoint
def batch_list():
    return _list(read_scope())


@read_endpoint
def batch_query():
    return _list(batch_scope(read_json_body(BODY)))


@read_endpoint
def batch_selection():
    query = batch_scope(read_json_body(BODY))
    if not query.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，还没有全选。请点「刷新」后重新点「全选当前筛选」。", 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    snapshot = None

    def bind(fingerprint):
        nonlocal snapshot
        snapshot = bind_read_snapshot(snapshot_scope(query), fingerprint, query["snapshot_ref"], as_of=reader.as_of)

    data, _ = reader.read_selection(query, bind=bind)
    return query_success(data, snapshot)


@api_endpoint
def batch_detail(ref):
    single_value_arguments({"snapshot_ref"}, message="详情的查询条件不对，详情没有打开。请刷新页面后重新点开这一行。")
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    snapshot = None

    def bind(fingerprint):
        nonlocal snapshot
        snapshot = bind_read_snapshot({"kind": "batch", "ref": ref}, fingerprint, request.args.get("snapshot_ref"), as_of=reader.as_of)

    with reader.facts.detached_read_snapshot(bind=bind, mode="single_template", target_ref=ref) as scope:
        data = entity_context(reader.detail(scope, ref), issue_write_context.for_snapshot(scope.fingerprint()))
    return query_success(data, snapshot)


@api_endpoint
def batch_choices():
    incomplete = "请选择完整的批次及工序后再读取候选资源。"
    args = single_value_arguments({"batch_ref", "operation_ref"}, message=incomplete)
    if bool(args.get("batch_ref")) != bool(args.get("operation_ref")):
        raise WorkbenchCommandRejected("invalid_input", incomplete, 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    choices_scope = {"kind": "batch_choices", **args}
    if not args:
        data = reader.choices_catalog()
        snapshot = bind_read_snapshot(choices_scope, data, as_of=reader.as_of)
    else:
        batch_ref = args["batch_ref"]
        with reader.facts.detached_read_snapshot(mode="single_choices", target_ref=batch_ref) as scope:
            data = reader.operation_choices(scope, batch_ref, args["operation_ref"])
            snapshot = bind_read_snapshot(choices_scope, scope.fingerprint(), as_of=reader.as_of)
    return query_success(data, snapshot)


@api_endpoint
def batch_command(action, ref=None):
    body = command_body(BODY, stale=STALE)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    domain = WorkbenchBatchService(g.db, current_app.logger)
    if action == "materials_update":
        normalized = normalize_material_changes(body["input"])
    else:
        normalized = normalize_operation_input(body["input"]) if action == "operation_update" else normalize_batch_input(action, body["input"])
    ref = None if action == "create" else public_ref(ref)
    subject = COLLECTION if ref is None else ref
    mode = "single_create" if ref is None else "single_instance"
    with reader.facts.command_snapshot(mode=mode, target_ref=ref) as scope:
        def guard():
            fingerprint = scope.fingerprint()
            if ref is not None:
                scope.resolve(ref)
            validate_write_context(body["write_token"], subject, "batch." + action, fingerprint)

        def mutate(_checked):
            if action == "materials_update":
                return WorkbenchBatchMaterialService(g.db, current_app.logger).apply_normalized(scope, ref, normalized)
            if action == "operation_update":
                operations = WorkbenchBatchOperationService(g.db)
                return operations.apply_update(operations.prepare_update(scope, ref, normalized))
            change = domain.preparation(scope).prepare(action, normalized, ref)
            return domain.apply_prepared(change)

        return json_response(WorkbenchCommandService(g.db, current_app.logger).execute(request_key=body["request_key"],
            action="batch." + action, context_ref=subject, normalized_input=normalized, guard=guard, mutate=mutate))


def _preview_scope_mode(action, payload):
    if action == "sync_confirm":
        return "single_template", None
    if action == "split_confirm":
        return "single_split", None
    if payload["action"] == "copy":
        return "batch_copy", tuple(payload["refs"])
    return "batch_closure", tuple(payload["refs"])


@read_endpoint
def batch_preview(action, ref=None):
    body = read_json_body(BODY)
    required = ("input", "snapshot_ref", "scope") if action == "bulk_confirm" else ("input", "snapshot_ref")
    object_fields(body, required, required)
    if not isinstance(body["snapshot_ref"], str) or not body["snapshot_ref"]:
        raise WorkbenchCommandRejected("invalid_input", "数据已更新，还没有保存。请刷新页面后" + retry_hint(action, body["input"]) + "。", 400)
    payload = (normalize_bulk(body["input"]) if action == "bulk_confirm" else
               normalize_split(body["input"]) if action == "split_confirm" else
               WorkbenchBatchOperationService.normalize_sync(body["input"]))
    query = batch_scope(body["scope"]) if action == "bulk_confirm" else None
    mode, target_refs = _preview_scope_mode(action, payload)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())

    def bind(fingerprint):
        if action in ("sync_confirm", "split_confirm"):
            bind_read_snapshot({"kind": "batch", "ref": ref}, fingerprint, body["snapshot_ref"], as_of=reader.as_of)
        else:
            bind_read_snapshot(snapshot_scope(query), fingerprint, body["snapshot_ref"], as_of=reader.as_of)

    with reader.facts.detached_read_snapshot(bind=bind, mode=mode, target_ref=ref, target_refs=target_refs) as scope:
        if action == "split_confirm":
            data = WorkbenchQuantitySplitService(g.db, current_app.logger).plan_normalized(scope, ref, payload)
            data["materials"] = [{"business_code": row["material_id"], **{key: value for key, value in row.items()
                                 if key not in ("requirement_id", "operation_id", "material_id")}} for row in data["materials"]]
        elif action == "sync_confirm":
            data = WorkbenchBatchOperationService(g.db).sync_preview_normalized(scope, ref)
        else:
            data = WorkbenchBatchBulkService(g.db, current_app.logger).plan_normalized(scope, payload)
        fingerprint = scope.fingerprint()
        preview, expires_at = save_preview(action, ref, payload, fingerprint, with_expiry=True)
        data.update(preview_ref=preview, expires_at=expires_at,
                    write_context=preview_write_context(preview, expires_at, ["batch." + action]))
        snapshot = bind_read_snapshot({"kind": "batch_preview", "preview_ref": preview}, fingerprint, as_of=reader.as_of)
    return query_success(data, snapshot)


@read_endpoint
def batch_facets():
    from core.models.workbench_batch import SORTS

    body = object_fields(read_json_body(BODY), ("scope", "field"), ("scope", "field"))
    query = batch_scope(body["scope"])
    if body["field"] not in SORTS or not query.get("snapshot_ref"):
        raise WorkbenchCommandRejected("invalid_input", "要筛选的列不对或数据已更新，筛选没有变化。请点「刷新」后重新打开列筛选。", 400)
    filters = {key: values for key, values in query["column_filters"].items() if key != body["field"]}
    facet_query = {**query, "column_filters": filters}
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    snapshot = None

    def bind(fingerprint):
        nonlocal snapshot
        snapshot = bind_read_snapshot(snapshot_scope(query), fingerprint, query["snapshot_ref"], as_of=reader.as_of)

    data, _ = reader.read_facets(facet_query, body["field"], bind=bind)
    return query_success(data, snapshot)


@api_endpoint
def batch_confirm(action, ref=None):
    body = command_body(BODY, stale=STALE)
    normalized = object_fields(body["input"], ("preview_ref",), ("preview_ref",))
    token = normalized["preview_ref"]
    if not isinstance(token, str) or not token:
        raise WorkbenchCommandRejected("invalid_input", retry_message(action, "预检结果编号缺失"), 400)
    reader = WorkbenchBatchQueryService(g.db, current_app.logger, as_of=current_snapshot_time())
    action_scope = None

    def guard():
        nonlocal action_scope
        binding = load_preview(token, action, ref)
        payload = binding["input"]
        mode, target_refs = _preview_scope_mode(action, payload)
        action_scope = BatchFactScope(
            reader.facts,
            command=True,
            mode=mode,
            target_ref=ref,
            target_refs=target_refs,
        )
        if binding["fingerprint"] != action_scope.fingerprint():
            raise WorkbenchCommandRejected("stale_write", retry_message(action, "预检之后资料有变化", payload))
        validate_preview_confirmation(body["write_token"], token)
        return payload, action_scope

    def mutate(checked):
        payload, scope = checked
        if action == "split_confirm":
            return WorkbenchQuantitySplitService(g.db, current_app.logger).apply_normalized(scope, ref, payload)
        if action == "bulk_confirm":
            return WorkbenchBatchBulkService(g.db, current_app.logger).apply_normalized(scope, payload)
        return WorkbenchBatchOperationService(g.db).sync_normalized(scope, ref)

    try:
        return json_response(WorkbenchCommandService(g.db, current_app.logger).execute(
            request_key=body["request_key"],
            action="batch." + action,
            context_ref=ref or token,
            normalized_input=normalized,
            guard=guard,
            mutate=mutate,
        ))
    finally:
        if action_scope is not None:
            action_scope.clear()


def register_batch_routes(bp):
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
