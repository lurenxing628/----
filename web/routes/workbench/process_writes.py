"""Process review and atomic stage confirmations using the shared receipt protocol."""

from flask import current_app, g, jsonify
from werkzeug.exceptions import HTTPException

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected, input_fingerprint, validate_request_key
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process_queries import WorkbenchProcessQueryService

from .api_responses import api_endpoint, query_success
from .process_json import read_process_json
from .read_context import bind_read_snapshot
from .write_context import issue_write_context, validate_write_context


def reviewed_input(action, normalized):
    if action == "route_confirm":
        return normalized["route"]
    return {key: value for key, value in normalized.items() if key != "discard_group_refs"}


@api_endpoint
def process_stage_preview(ref):
    from core.services.workbench.process_mutations import WorkbenchProcessMutationService

    try:
        body = read_process_json("归属检查", 4 * 1024 * 1024)
        if set(body) != {"action", "input", "snapshot_ref"} or body["action"] != "source_confirm":
            raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，归属没有保存。请刷新页面后重新点「检查归属」。", 400)
        domain = WorkbenchProcessMutationService(g.db, current_app.logger)
        normalized = domain.normalize(body["action"], body["input"])
        reader = WorkbenchProcessQueryService(g.db, current_app.logger)
        with reader.read_snapshot() as state:
            entity = reader.detail(ref)
            bind_read_snapshot({"kind": "part", "entity_ref": ref}, state, body["snapshot_ref"])
            if entity["workflow"]["route"]["state"] != "confirmed":
                raise WorkbenchCommandRejected("stage_locked", "工艺路线还没有确认，归属没有保存。请先点「确认保存路线」，再点「检查归属」。")
            affected = set(domain.affected_groups("source_confirm", normalized, reader.resolve(ref)))
            binding = {"state": state, "input": reviewed_input("source_confirm", normalized)}
            data = {"part_ref": ref, "action": "source_confirm",
                    "affected_groups": [row for row in entity["external_groups"] if row["ref"] in affected],
                    "write_context": issue_write_context(ref, ["process.source_confirm"], binding)}
            snapshot = bind_read_snapshot({"kind": "process_stage_preview", "entity_ref": ref,
                                           "input_hash": input_fingerprint(normalized)}, state)
        response = query_success(data, snapshot)
        response.headers["Cache-Control"] = "no-store"
        return response
    except (WorkbenchCommandRejected, AppError, HTTPException):
        raise
    except Exception as exc:
        raise WorkbenchCommandRejected("storage_failure", "归属检查没有完成，工艺资料没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500) from exc


@api_endpoint
def process_stage_command(ref, action):
    from core.services.workbench.process_mutations import WorkbenchProcessMutationService

    if action not in ("route_confirm", "source_confirm", "hours_confirm"):
        raise WorkbenchCommandRejected("invalid_input", "这个操作入口不对，工艺资料没有改动。请刷新页面后重试。", 400)
    body = read_process_json("工艺保存", 4 * 1024 * 1024)
    if set(body) != {"request_key", "write_token", "input"}:
        raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，工艺资料还没有保存。请刷新页面后重新填写。", 400)
    validate_request_key(body["request_key"])
    g.workbench_request_key = body["request_key"]
    if type(body["write_token"]) is not str or not body["write_token"]:
        raise WorkbenchCommandRejected("invalid_input", "本页数据已过期，工艺资料还没有保存。请点「刷新资料」后重新核对再保存。", 400)
    domain = WorkbenchProcessMutationService(g.db, current_app.logger)
    normalized = domain.normalize(action, body["input"])
    reader = WorkbenchProcessQueryService(g.db, current_app.logger)

    def guard():
        with reader.read_snapshot() as state:
            identity = reader.resolve(ref)
            binding = state if action == "hours_confirm" else {"state": state, "input": reviewed_input(action, normalized)}
            validate_write_context(body["write_token"], ref, "process." + action, binding)
            return identity

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action="process." + action, context_ref=ref,
        normalized_input=normalized, guard=guard, mutate=lambda identity: domain.apply(action, normalized, identity))
    return jsonify(outcome)


def register_process_write_routes(bp):
    bp.add_url_rule("/api/workbench/v1/process/<ref>/stage-preview", view_func=process_stage_preview, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/process/<ref>/<action>", view_func=process_stage_command, methods=["POST"])
