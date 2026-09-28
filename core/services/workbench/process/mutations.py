"""Process actions inside the caller's BEGIN IMMEDIATE and receipt transaction."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_commands import normalize_process_input
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository
from data.repositories.workbench_process_query_repo import WorkbenchProcessQueryRepository

from .group_apply import apply_groups, group_changes, prepare_groups
from .group_defaults import apply_default_groups
from .projection import require_ref
from .route_apply import affected_group_rows, apply_route, discard_groups, prepare_route, require_group_ack
from .stage_apply import apply_hours, apply_source, prepare_source, source_group_changes


class WorkbenchProcessMutationService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.repo = WorkbenchProcessQueryRepository(conn, logger)
        self.identities = WorkbenchIdentityRepository(conn, logger)

    @staticmethod
    def normalize(action, input):
        return normalize_process_input(action, input)

    def _snapshot(self, identity):
        if not isinstance(identity, WorkbenchEntityIdentity) or identity.kind != "part":
            raise WorkbenchCommandRejected("invalid_input", "请先选定零件再操作。", 400)
        current = self.identities.get(identity.ref)
        if not identity.active or current is None or not current.active or current.kind != "part":
            raise WorkbenchCommandRejected("entity_not_found", "这条零件记录已失效。请刷新列表后重新选择。", 404)
        if current != identity:
            raise WorkbenchCommandRejected("stale_write", "零件资料已经变了。请刷新后重新核对。")
        part = self.repo.part_by_no(current.entity_key)
        if part is None:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件不存在。请刷新列表后重新选择。", 404)
        operations = self.repo.template_operations_with_refs(current.entity_key)
        groups = self.repo.template_groups_with_refs(current.entity_key)
        self._check_template(operations, groups, current.entity_key)
        return part, operations, groups

    def _check_template(self, operations, groups, part_no):
        group_keys = {row["group_id"] for row in groups}
        for row in operations:
            require_ref(row["ref"], "模板工序")
            if row["status"] not in ("active", "deleted") or type(row["seq"]) is not int or row["seq"] <= 0:
                raise WorkbenchCommandRejected("template_invalid", "原工序的序号或状态说不清。请到基础资料核对工序。", 422)
            if row["ext_group_id"] is not None and row["ext_group_id"] not in group_keys:
                raise WorkbenchCommandRejected("group_invalid", "原工序关联外协组不存在或属于其他零件，请先核对资料。", 422)
        for row in groups:
            require_ref(row["ref"], "模板外协组")
            if type(row["start_seq"]) is not int or type(row["end_seq"]) is not int or not 0 < row["start_seq"] <= row["end_seq"]:
                raise WorkbenchCommandRejected("group_invalid", "原外协组的工序范围说不清，算不准影响面。请到基础资料核对外协组起止序。", 422)
        if self.repo.foreign_group_use_exists(part_no):
            raise WorkbenchCommandRejected("group_invalid", "这个外协组还被别的零件工序用着，不能在当前零件解除。请先到那些零件上解除。", 422)

    def _prepare(self, action, payload, operations, groups):
        if action == "route_confirm":
            prepared, sequences = prepare_route(self.conn, self.logger, payload, operations)
            return prepared, affected_group_rows(groups, operations, sequences)
        prepared, _ = prepare_source(self.conn, self.logger, payload, operations, self.identities)
        affected, _ = source_group_changes(prepared, operations, groups)
        return prepared, affected

    def preview_groups(self, input, identity):
        payload = self.normalize("groups_confirm", input)
        _, operations, groups = self._snapshot(identity)
        prepared, discarded = prepare_groups(self.conn, payload, operations, groups, self.identities)
        return group_changes(self.conn, prepared, discarded, operations)

    def affected_groups(self, action, input, identity):
        """Read-only preview; caller owns a consistent read snapshot and token scope.

        Returns sorted permanent refs. Does not require an acknowledgement yet;
        apply re-reads the same facts and checks the exact set under the write lock.
        """
        payload = self.normalize(action, input)
        if action not in ("route_confirm", "source_confirm"):
            raise WorkbenchCommandRejected("invalid_input", "仅路线和归属操作会解除外协组。", 400)
        _, operations, groups = self._snapshot(identity)
        _, affected = self._prepare(action, payload, operations, groups)
        return sorted(row["ref"] for row in affected)

    def _apply_group_action(self, payload, identity, part, operations, groups, workflow):
        from core.services.process.workflow_state import record_confirmation

        if workflow["route"]["state"] != "confirmed":
            raise WorkbenchCommandRejected("stage_not_ready", "请先确认路线，再维护外协段。")
        prepared, discarded = prepare_groups(self.conn, payload, operations, groups, self.identities)
        changed = apply_groups(self.conn, part["part_no"], prepared, discarded, operations)
        if changed and workflow["source"]["state"] == "confirmed":
            record_confirmation(self.conn, part["part_no"], "source")
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {
            "entity_ref": identity.ref, "business_code": part["part_no"], "stage": "groups"})

    def _apply_source_changes(self, part_no, prepared, operations, groups):
        _, supplier_updates = source_group_changes(prepared, operations, groups)
        apply_source(self.conn, prepared, operations)
        for group_id, supplier_id in supplier_updates:
            ExternalGroupRepository(self.conn).update(group_id, {"supplier_id": supplier_id})
        by_id = {row["id"]: row for row in operations}
        new_external = {by_id[change[3]]["seq"] for change in prepared if change[0] == "external"
            and (by_id[change[3]]["source"] != "external" or by_id[change[3]]["op_type_id"] != change[1]
                 or by_id[change[3]]["supplier_id"] is None)
            and by_id[change[3]]["ext_group_id"] is None}
        grouped = apply_default_groups(self.conn, part_no, new_external)
        return bool(prepared or supplier_updates or grouped)

    def apply(self, action, input, identity):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺动作必须在外层BEGIN IMMEDIATE命令事务内执行。")
        payload = self.normalize(action, input)
        part, operations, groups = self._snapshot(identity)
        # Separate owner installs the schema and implements signature revalidation.
        from core.services.process.workflow_state import read_workflow, record_confirmation

        stage = action[:-len("_confirm")]
        workflow = read_workflow(self.conn, part["part_no"])
        if stage == "groups":
            return self._apply_group_action(payload, identity, part, operations, groups, workflow)
        if stage != "route":
            previous = "route" if stage == "source" else "source"
            if workflow[previous]["state"] != "confirmed":
                raise WorkbenchCommandRejected("stage_not_ready", "前置阶段尚未确认或已变化，请先重新核对。")
        if stage == "hours":
            changed = apply_hours(self.conn, payload, operations, groups)
        else:
            prepared, affected = self._prepare(action, payload, operations, groups)
            require_group_ack(payload, affected)
            discard_groups(self.conn, part["part_no"], affected)
            if stage == "route":
                changed = apply_route(self.conn, part, operations, prepared, self.identities) or bool(affected)
            else:
                changed = self._apply_source_changes(part["part_no"], prepared, operations, groups) or bool(affected)
        result = "unchanged" if not changed and workflow[stage]["state"] == "confirmed" else "committed"
        # Route confirmation also retires records for removed operations.
        if result != "unchanged" or stage == "route":
            record_confirmation(self.conn, part["part_no"], stage)
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref,
                                                "business_code": part["part_no"], "stage": stage})
