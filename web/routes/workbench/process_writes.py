"""Process review and atomic stage confirmations using the shared receipt protocol."""

from collections import defaultdict

from flask import current_app, g
from werkzeug.exceptions import HTTPException

from core.errors import AppError
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.process.workflow_state import confirmation_stamp
from core.services.workbench.commands import WorkbenchCommandService
from core.services.workbench.process.projection import project_group
from core.services.workbench.process.queries import WorkbenchProcessQueryService
from core.shared.key_sets import keys_conform
from web.api_responses import json_response, query_success
from web.runtime_host import wall_clock

from .api_responses import api_endpoint, read_endpoint
from .process_action_context import PROCESS_INCOMPLETE, PROCESS_STALE
from .process_json import process_command_body, read_process_json
from .read_context import bind_read_snapshot, current_snapshot_time
from .write_context import issue_write_context, validate_write_context


def reviewed_input(action, normalized):
    if action == "route_confirm":
        return normalized["route"]
    return {key: value for key, value in normalized.items() if key != "discard_group_refs"} if action == "source_confirm" else normalized


@read_endpoint
def process_stage_preview(ref):
    from core.services.workbench.process.mutations import WorkbenchProcessMutationService

    try:
        body = read_process_json("归属检查", 4 * 1024 * 1024)
        if not keys_conform(body, ("action", "input", "snapshot_ref")) or body["action"] not in ("source_confirm", "groups_confirm"):
            raise WorkbenchCommandRejected("invalid_input", "提交的内容不完整或有多余项，归属没有保存。请刷新页面后重新点「保存归属并继续」。", 400)
        now = current_snapshot_time()
        domain = WorkbenchProcessMutationService(g.db, current_app.logger)
        normalized = domain.normalize(body["action"], body["input"])
        reader = WorkbenchProcessQueryService(g.db, current_app.logger, part_ref=ref)
        with reader.read_snapshot() as scope:
            state = scope.state_fingerprint()
            identity = scope.resolve(ref)
            bind_read_snapshot({"kind": "part", "entity_ref": ref}, state, body["snapshot_ref"], as_of=now)
            facts = scope.facts()
            checked = domain.checked_facts(identity, facts)
            _, _, operations, _, workflow = checked
            if workflow["route"]["state"] != "confirmed":
                raise WorkbenchCommandRejected("stage_locked", "工艺路线还没有确认，归属没有保存。请先点「确认保存路线」，再点「保存归属并继续」。")
            action = body["action"]
            prepared = domain.prepare_review(action, normalized, checked, facts=facts)
            if action == "source_confirm" and prepared.affected:
                group_ids = {row["group_id"] for row in prepared.affected}
                members = defaultdict(list)
                for operation in operations:
                    if operation["status"] == "active" and operation["ext_group_id"] in group_ids:
                        members[operation["ext_group_id"]].append(operation)
                affected_groups = [project_group(row, members[row["group_id"]]) for row in prepared.affected]
            else:
                affected_groups = []
            binding = {"state": state, "input": reviewed_input(action, normalized)}
            data = {"part_ref": ref, "action": action,
                    "affected_groups": affected_groups,
                    "write_context": issue_write_context(ref, ["process." + action], binding)}
            if action == "groups_confirm":
                data["changes"] = prepared.auxiliary
            snapshot = bind_read_snapshot({"kind": "process_stage_preview", "entity_ref": ref,
                                           "input_content": normalized}, state, as_of=now)
        return query_success(data, snapshot)
    except (AppError, HTTPException, WorkbenchCommandRejected):
        raise
    except Exception as exc:
        raise WorkbenchCommandRejected("storage_failure", "归属检查没有完成，工艺资料没有改动。请刷新重试；仍不行请联系维护人员，并告知下方编号。", 500) from exc


@api_endpoint
def process_stage_command(ref, action):
    from core.services.workbench.process.mutations import WorkbenchProcessMutationService

    if action not in ("route_confirm", "source_confirm", "hours_confirm", "groups_confirm"):
        raise WorkbenchCommandRejected("invalid_input", "这个操作入口不对，工艺资料没有改动。请刷新页面后重试。", 400)
    body = process_command_body("工艺保存", 4 * 1024 * 1024, incomplete=PROCESS_INCOMPLETE, stale=PROCESS_STALE)
    domain = WorkbenchProcessMutationService(g.db, current_app.logger)
    normalized = domain.normalize(action, body["input"])
    reader = WorkbenchProcessQueryService(g.db, current_app.logger, part_ref=ref)

    def guard():
        with reader.read_snapshot() as scope:
            state = scope.state_fingerprint()
            identity = scope.resolve(ref)
            binding = state if action == "hours_confirm" else {"state": state, "input": reviewed_input(action, normalized)}
            validate_write_context(body["write_token"], ref, "process." + action, binding)
            facts = scope.facts()
            checked = domain.checked_facts(identity, facts)
            return domain.prepare_checked(action, normalized, checked, facts=facts)

    outcome = WorkbenchCommandService(g.db, current_app.logger).execute(
        request_key=body["request_key"], action="process." + action, context_ref=ref,
        normalized_input=normalized, guard=guard,
        mutate=lambda prepared: domain.apply_prepared(prepared, confirmed_at=confirmation_stamp(wall_clock(current_app)())))
    return json_response(outcome)


def register_process_write_routes(bp):
    bp.add_url_rule("/api/workbench/v1/process/<ref>/stage-preview", view_func=process_stage_preview, methods=["POST"])
    bp.add_url_rule("/api/workbench/v1/process/<ref>/<action>", view_func=process_stage_command, methods=["POST"])
