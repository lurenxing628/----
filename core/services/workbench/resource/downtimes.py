"""Guarded downtime maintenance; cancellation retains the original record."""

from core.models.workbench_command import WorkbenchCommandOutcome, WorkbenchCommandRejected
from core.models.workbench_downtime import REASONS, normalize_downtime
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
        record = self.reader.detail(ref)
        rows = self.facts.rows(record.identity.entity_key)
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "停机记录的系统编号不完整，请联系维护人员核对。", 503)
        return {"machine": record.state, "machine_id": record.identity.entity_key, "rows": rows}

    @staticmethod
    def public(state):
        keys = ("ref", "start_time", "end_time", "reason_code", "reason_detail", "status")
        return {"rows": [{key: row[key] for key in keys} for row in state["rows"]], "reasons": REASONS}

    def apply(self, ref, action, payload, state):
        if not self.conn.in_transaction:
            raise RuntimeError("停机维护必须在工作台命令事务内执行。")
        payload = normalize_downtime(action, payload)
        row = self._target(action, payload, state)
        if action == "cancel":
            if row is None:
                raise RuntimeError("取消停机前必须核对原记录。")
            self.repo.cancel(row["id"])
            return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": row["ref"]})
        return self._save(ref, action, payload, state, row)

    @staticmethod
    def _target(action, payload, state):
        row = None
        if action != "create":
            row = next((row for row in state["rows"] if row["ref"] == payload["downtime_ref"]), None)
            if row is None:
                raise WorkbenchCommandRejected("entity_not_found", "停机记录已失效或不属于该设备，请刷新后重新选择。", 404)
            if row["status"] != "active":
                raise WorkbenchCommandRejected("constraint_conflict", "这条停机记录已经取消，不能再修改。")
        return row

    def _save(self, ref, action, payload, state, row):
        fields = {key: value for key, value in payload.items() if key != "downtime_ref"}
        if self.repo.has_overlap(state["machine_id"], fields["start_time"], fields["end_time"], row["id"] if row else None):
            raise WorkbenchCommandRejected("constraint_conflict", "该设备已有与此时间重叠的有效停机记录，请核对起止时间。")
        if row is None:
            created = self.repo.create({**fields, "machine_id": state["machine_id"], "scope_type": "machine",
                                        "scope_value": state["machine_id"], "status": "active"})
            new = next(item for item in self.facts.rows(state["machine_id"]) if item["id"] == created.id)
            return WorkbenchCommandOutcome("committed", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": new["ref"]})
        changed = any(row[key] != value for key, value in fields.items())
        if changed:
            self.repo.update(row["id"], fields)
        return WorkbenchCommandOutcome("committed" if changed else "unchanged", {"entity_ref": ref, "operation": "machine.downtime_" + action, "downtime_ref": row["ref"]})
