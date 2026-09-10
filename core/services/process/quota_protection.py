"""Shared process quota protection; locks belong to the original template ref."""

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.base_repo import BaseRepository
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository
from data.repositories.workbench_execution_repo import chunks


def quota_skip(ref, lock):
    return {"code": "calibration_quota_locked", "template_operation_ref": ref,
            "adoption_ref": lock["adoption_ref"], "reason": lock["reason"],
            "message": "已采纳的单件定额已锁定，本行跳过；锁仅属于原模板永久引用。"}


def quota_skip_summary(rows):
    skipped = [{"row": row["row"], **row["skip_reason"]} for row in rows if row["result"] == "skipped"]
    return {"skipped_count": len(skipped), "skipped_refs": [row["template_operation_ref"] for row in skipped],
            "skipped_rows": skipped}


class ProcessQuotaProtection:
    def __init__(self, conn):
        self.conn = conn
        self.repo = BaseRepository(conn)
        self.locks = WorkbenchCalibrationAdoptionRepository(conn)

    def read_locks(self, refs):
        # Missing/partial DDL and damaged audit pairs are errors even for no changes.
        return self.locks.read_locks(refs)

    def bind(self, part_no, seq):
        self.read_locks([])
        row = self.repo.fetchone("""SELECT r.ref FROM PartOperations o LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='template_operation' AND r.entity_key=CAST(o.id AS TEXT) AND r.active=1
            WHERE o.part_no=? AND o.seq=? AND o.status='active'""", (part_no, seq))
        if row is None or row["ref"] is None:
            raise WorkbenchCommandRejected("entity_not_found", "模板永久引用缺失或已失效，不能按同号新对象补配。", 404)
        return row["ref"]

    def current(self, refs):
        refs = sorted(set(refs))
        locks = self.read_locks(refs)
        result = {}
        for chunk in chunks(refs):
            rows = self.repo.fetchall("""SELECT o.*,r.ref,r.revision FROM WorkbenchEntityRefs r
                JOIN PartOperations o ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.status='active'
                AND r.ref IN (""" + ",".join("?" for _ in chunk) + ")", chunk)
            result.update((row["ref"], row) for row in rows)
        if set(result) != set(refs):
            raise WorkbenchCommandRejected("stale_write", "原模板引用已失效，未重新绑定同图号同序号的新模板。")
        for ref, lock in locks.items():
            if result[ref]["unit_hours"] != lock["locked_unit_hours"]:
                raise WorkbenchCommandRejected("calibration_lock_corrupt", "模板定额与采纳锁不一致，未按未锁定处理。", 500)
        return result, locks

    def require_changes(self, values):
        """Validate proposed unit_hours against live rows, not a caller's old snapshot."""
        if not self.conn.in_transaction:
            raise RuntimeError("普通定额保存必须在调用方写事务中重核。")
        current, locks = self.current(values)
        if any(ref in locks and value != current[ref]["unit_hours"] for ref, value in values.items()):
            raise WorkbenchCommandRejected("calibration_quota_locked", "已采纳的单件定额已锁定，普通保存不能覆盖。")
        return current

    def legacy_metadata(self):
        rows = self.repo.fetchall("""SELECT o.part_no,o.seq,o.unit_hours,r.ref FROM PartOperations o
            LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
            AND r.entity_key=CAST(o.id AS TEXT) WHERE o.status='active' ORDER BY o.part_no,o.seq""")
        locks = self.read_locks([row["ref"] for row in rows if row["ref"] is not None])
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "工时导入的原模板永久引用缺失，未按业务编号补配。", 500)
        if any(row["ref"] in locks and row["unit_hours"] != locks[row["ref"]]["locked_unit_hours"] for row in rows):
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "模板定额与采纳锁不一致，未按未锁定处理。", 500)
        return {"{}|{}".format(row["part_no"], row["seq"]):
                {"template_operation_ref": row["ref"], "quota_lock": locks.get(row["ref"])} for row in rows}
