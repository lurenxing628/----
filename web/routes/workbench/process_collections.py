"""Process collection mutations with exact preview selection and shared receipts."""

from flask import current_app, g, jsonify

from core.models.workbench_command import WorkbenchCommandRejected, validate_request_key
from core.models.workbench_process_actions import process_part_refs, process_part_scope
from core.models.workbench_process_query import ProcessPageRequest
from core.models.workbench_process_table_query import ProcessTablePageRequest
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_part_actions import WorkbenchProcessPartActionService
from core.services.workbench.process_queries import WorkbenchProcessQueryService

from .api_responses import api_endpoint, query_success
from .process_action_context import action_preview, checked_preview, confirmed_body
from .process_json import read_process_json
from .read_context import bind_read_snapshot
from .resource_action_context import read_endpoint
from .write_context import validate_write_context

DELETE_COLUMNS = (("business_code", "图号"), ("label", "零件名称"), ("route_raw", "原始路线"),
                  ("route_parsed", "路线解析标记"), ("remark", "备注"),
                  ("operation_count", "工序数量"), ("external_group_count", "外协组数量"))


def collection_scope(scope, size=20):
    normalized = process_part_scope(scope)
    query_type = ProcessTablePageRequest if "column_filters" in normalized or type(normalized.get("sort")) is list else ProcessPageRequest
    return normalized, query_type(**normalized, size=size).scope()


@api_endpoint
def process_create():
    body = read_process_json("新增零件", 1024 * 1024)
    if set(body) != {"request_key", "write_token", "input"}:
        raise WorkbenchCommandRejected("invalid_input", "新增零件请求字段不正确。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    domain = WorkbenchProcessPartActionService(g.db, current_app.logger)
    payload = domain.normalize_create(body["input"])
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)

    def guard():
        with reader.read_snapshot() as state:
            validate_write_context(body["write_token"], "process:create", "process.create", state)

    result = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action="process.create", context_ref="process:create",
        normalized_input=payload, guard=guard, mutate=lambda _: domain.create(payload))
    return jsonify(result)


@read_endpoint
def process_bulk_preview():
    body = read_process_json("删除预检", 4 * 1024 * 1024)
    if not {"refs", "scope", "snapshot_ref"} <= set(body) or set(body) - {"refs", "scope", "snapshot_ref", "page_size"}:
        raise WorkbenchCommandRejected("invalid_input", "删除预检字段不正确。", 400)
    if type(body["snapshot_ref"]) is not str or not body["snapshot_ref"]:
        raise WorkbenchCommandRejected("snapshot_stale", "删除预检需要原列表快照，请先重新读取列表。")
    refs = process_part_refs(body["refs"])
    scope, query_scope = collection_scope(body["scope"], body.get("page_size", 20))
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)
    with reader.read_snapshot() as state:
        snapshot = bind_read_snapshot(query_scope, state, body["snapshot_ref"])
        preview = WorkbenchProcessPartActionService(g.db, current_app.logger).preview_delete(refs, scope=scope)
        result = action_preview(preview, "process_bulk.confirm", extra={
            "columns": [{"key": key, "label": label} for key, label in DELETE_COLUMNS]})
    return query_success(result, snapshot)


@api_endpoint
def process_bulk_confirm():
    body = confirmed_body({"preview_ref"})
    ref = body["input"]["preview_ref"]

    def apply(checked):
        preview, _ = checked
        original = preview.as_dict()["request"]
        return WorkbenchProcessPartActionService(g.db, current_app.logger).confirm_delete(preview, original["refs"], scope=original["scope"])

    result = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action="process_bulk.confirm", context_ref=ref, normalized_input=body["input"],
        guard=lambda: checked_preview(ref, "part.bulk_delete", "process_bulk.confirm", body["write_token"]), mutate=apply)
    return jsonify(result)


def register_process_collection_routes(bp):
    bp.add_url_rule("/api/workbench/v1/process/parts/create", view_func=process_create, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/process/parts/bulk-preview", view_func=process_bulk_preview, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/process/parts/bulk-confirm", view_func=process_bulk_confirm, methods=["POST"])
