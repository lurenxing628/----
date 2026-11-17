"""Guarded downtime maintenance; cancellation retains the original record."""

from core.models.enums import MACHINE_DOWNTIME_REASON_LABELS
from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from data.repositories.machine_downtime_repo import MachineDowntimeRepository
from data.repositories.workbench_downtime_repo import WorkbenchDowntimeRepository

from .queries import WorkbenchResourceQueryService


class WorkbenchDowntimeService:
    def __init__(self, conn, logger=None):
        self.conn = conn
        self.reader = WorkbenchResourceQueryService(conn, "machine", logger)
        self.facts = WorkbenchDowntimeRepository(conn, logger)
        self.repo = MachineDowntimeRepository(conn, logger)

    def snapshot(self, ref):
        identity = self.reader.resolve(ref)
        state = self.reader.current_with_identity(identity)
        rows = self.facts.rows(identity.entity_key)
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "停机记录的系统编号不完整，请联系维护人员核对。", 503)
        return {"machine": state, "machine_id": identity.entity_key, "rows": rows}

    @staticmethod
    def public(state):
        keys = ("ref", "start_time", "end_time", "reason_code", "reason_detail", "status")
        return {"rows": [{key: row[key] for key in keys} for row in state["rows"]], "reasons": MACHINE_DOWNTIME_REASON_LABELS}

    def apply_normalized(self, ref, action, payload, state):
        if not self.conn.in_transaction:
            raise RuntimeError("停机维护必须在工作台命令事务内执行。")
        if action == "cancel":
            row = self._target(payload, state)
            self.repo.cancel(row["id"])
            return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": row["ref"]})
        row = None if action == "create" else self._target(payload, state)
        return self._save(ref, action, payload, state, row)

    @staticmethod
    def _target(payload, state):
        row = next((row for row in state["rows"] if row["ref"] == payload["downtime_ref"]), None)
        if row is None:
            raise WorkbenchCommandRejected("entity_not_found", "停机记录已失效或不属于该设备，请刷新后重新选择。", 404)
        if row["status"] == "cancelled":
            raise WorkbenchCommandRejected("constraint_conflict", "这条停机记录已经取消，不能再修改。")
        return row

    def _save(self, ref, action, payload, state, row):
        fields = {key: value for key, value in payload.items() if key != "downtime_ref"}
        start_us, end_us = fields["start_us"], fields["end_us"]
        # 只在起止变了时查同设备有效停机的重叠；只改原因或说明的不受已有重叠影响。
        if row is None or (row["start_us"], row["end_us"]) != (start_us, end_us):
            for existing in state["rows"]:
                if existing["status"] != "active" or row is not None and existing["id"] == row["id"]:
                    continue
                if existing["end_us"] > start_us and existing["start_us"] < end_us:
                    raise WorkbenchCommandRejected("constraint_conflict", "该设备已有与此时间重叠的有效停机记录，请核对起止时间。")
        if row is None:
            created_id = self.repo.create({**fields, "machine_id": state["machine_id"], "scope_type": "machine",
                                           "scope_value": state["machine_id"], "status": "active"})
            return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": self.facts.ref_for_id(created_id)})
        changed = any(row[key] != value for key, value in fields.items())
        if changed:
            self.repo.update(row["id"], fields)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": row["ref"]})
