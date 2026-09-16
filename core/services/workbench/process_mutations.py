"""Process actions inside the caller's BEGIN IMMEDIATE and receipt transaction."""

from __future__ import annotations

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_identity import WorkbenchEntityIdentity
from core.models.workbench_process_commands import normalize_process_input
from core.services.workbench.process_projection import require_ref
from core.services.workbench.process_route_apply import (
    affected_group_rows,
    apply_route,
    discard_groups,
    prepare_route,
    require_group_ack,
)
from core.services.workbench.process_stage_apply import apply_hours, apply_source, prepare_source
from data.repositories.base_repo import BaseRepository
from data.repositories.workbench_identity_repo import WorkbenchIdentityRepository


class WorkbenchProcessMutationService:
    def __init__(self, conn, logger=None):
        self.conn, self.logger = conn, logger
        self.repo = BaseRepository(conn, logger)
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
        part = self.repo.fetchone("SELECT * FROM Parts WHERE part_no=?", (current.entity_key,))
        if part is None:
            raise WorkbenchCommandRejected("entity_not_found", "这个零件不存在。请刷新列表后重新选择。", 404)
        operations = self.repo.fetchall("""SELECT o.*,r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            WHERE o.part_no=? ORDER BY o.seq""", (current.entity_key,))
        groups = self.repo.fetchall("""SELECT g.*,r.ref FROM ExternalGroups g LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_external_group' AND r.entity_key=g.group_id AND r.active=1
            WHERE g.part_no=? ORDER BY g.start_seq,g.group_id""", (current.entity_key,))
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
        if self.repo.fetchone("""SELECT 1 FROM PartOperations o JOIN ExternalGroups g ON g.group_id=o.ext_group_id
            WHERE g.part_no=? AND o.part_no<>? LIMIT 1""", (part_no, part_no)):
            raise WorkbenchCommandRejected("group_invalid", "这个外协组还被别的零件工序用着，不能在当前零件解除。请先到那些零件上解除。", 422)

    def _prepare(self, action, payload, operations, groups):
        if action == "route_confirm":
            prepared, sequences = prepare_route(self.conn, self.logger, payload, operations)
        else:
            prepared, sequences = prepare_source(self.conn, self.logger, payload, operations, self.identities)
        return prepared, affected_group_rows(groups, operations, sequences)

    def affected_groups(self, action, input, identity):
        """Read-only preview; caller owns a consistent read snapshot and token scope.

        Returns sorted permanent refs. Does not require an acknowledgement yet;
        apply re-reads the same facts and checks the exact set under the write lock.
        """
        payload = self.normalize(action, input)
        if action == "hours_confirm":
            raise WorkbenchCommandRejected("invalid_input", "仅路线和归属操作会解除外协组。", 400)
        _, operations, groups = self._snapshot(identity)
        _, affected = self._prepare(action, payload, operations, groups)
        return sorted(row["ref"] for row in affected)

    def apply(self, action, input, identity):
        if not self.conn.in_transaction:
            raise RuntimeError("工艺动作必须在外层BEGIN IMMEDIATE命令事务内执行。")
        payload = self.normalize(action, input)
        part, operations, groups = self._snapshot(identity)
        # Separate owner installs the schema and implements signature revalidation.
        from core.services.process.workflow_state import read_workflow, record_confirmation

        stage = action[:-len("_confirm")]
        workflow = read_workflow(self.conn, part["part_no"])
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
                apply_source(self.conn, prepared)
                changed = bool(prepared or affected)
        result = "unchanged" if not changed and workflow[stage]["state"] == "confirmed" else "committed"
        # Route confirmation also retires records for removed operations.
        if result != "unchanged" or stage == "route":
            record_confirmation(self.conn, part["part_no"], stage)
        return WorkbenchCommandOutcome(result, {"entity_ref": identity.ref,
                                                "business_code": part["part_no"], "stage": stage})
