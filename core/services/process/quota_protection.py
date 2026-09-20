"""Shared process quota protection; locks belong to the original template ref.

The adoption repository only returns storage facts; every ruling about missing DDL,
bad input, oversized queries and corrupt audit/lock pairs is decided here.
"""

from core.models.workbench_calibration import MAX_TEMPLATES
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_execution_input import public_ref
from data.repositories.process_query_repo import ProcessQueryRepository
from data.repositories.workbench_calibration_adoption_repo import WorkbenchCalibrationAdoptionRepository


def quota_skip(ref, lock):
    return {"code": "calibration_quota_locked", "template_operation_ref": ref,
            "adoption_ref": lock["adoption_ref"], "reason": lock["reason"],
            "message": "已采纳的单件定额已锁定，本行跳过；锁仅属于原模板永久引用。"}


def quota_skip_summary(rows):
    skipped = [{"row": row["row"], **row["skip_reason"]} for row in rows if row["result"] == "skipped"]
    return {"skipped_count": len(skipped), "skipped_refs": [row["template_operation_ref"] for row in skipped],
            "skipped_rows": skipped}


def require_adoption_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "采纳存储尚未安装或结构不完整，本次没有自动补表。", 503)


def read_quota_locks(repo, template_operation_refs):
    """Return {permanent_ref: lock}; absent key means unlocked only with valid DDL.

    Ordinary writes/imports must call inside their own write transaction. Missing or
    partial DDL and damaged audit pairs are errors even for an empty ref set.
    """
    require_adoption_schema(repo)
    if isinstance(template_operation_refs, (str, bytes)):
        raise WorkbenchCommandRejected("invalid_input", "定额锁查询必须提供模板永久引用集合。", 400)
    refs = sorted({public_ref(ref) for ref in template_operation_refs})
    if len(refs) > MAX_TEMPLATES:
        raise WorkbenchCommandRejected("query_too_large", "定额锁查询最多10000个模板引用，未截断。", 413)
    result = {}
    for audited, rows in repo.lock_pairs(refs):
        if audited != {row["template_operation_ref"] for row in rows}:
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "采纳审计与定额锁不成对，未按未锁定处理。", 500)
        for row in rows:
            if (row["audit_template_ref"] != row["template_operation_ref"] or row["new_unit_hours"] != row["locked_unit_hours"]
                    or row["adopted_at"] != row["locked_at"]):
                raise WorkbenchCommandRejected("calibration_lock_corrupt", "定额锁内容与采纳审计不一致，未按未锁定处理。", 500)
            result[row["template_operation_ref"]] = {key: value for key, value in row.items()
                if key not in ("audit_template_ref", "new_unit_hours", "adopted_at")}
            result[row["template_operation_ref"]]["locked"] = True
            result[row["template_operation_ref"]]["confirmed"] = row["confirmed"] == 1
    return result


class ProcessQuotaProtection:
    def __init__(self, conn):
        self.conn = conn
        self.repo = ProcessQueryRepository(conn)
        self.locks = WorkbenchCalibrationAdoptionRepository(conn)

    def read_locks(self, refs):
        # Missing/partial DDL and damaged audit pairs are errors even for no changes.
        return read_quota_locks(self.locks, refs)

    def bind(self, part_no, seq):
        self.read_locks([])
        row = self.repo.template_operation_ref(part_no, seq)
        if row is None or row["ref"] is None:
            raise WorkbenchCommandRejected("entity_not_found", "模板永久引用缺失或已失效，不能按同号新对象补配。", 404)
        return row["ref"]

    def current(self, refs):
        refs = sorted(set(refs))
        locks = self.read_locks(refs)
        result = {row["ref"]: row for row in self.repo.template_operations_by_refs(refs)}
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
        rows = self.repo.legacy_template_operations()
        locks = self.read_locks([row["ref"] for row in rows if row["ref"] is not None])
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "工时导入的原模板永久引用缺失，未按业务编号补配。", 500)
        if any(row["ref"] in locks and row["unit_hours"] != locks[row["ref"]]["locked_unit_hours"] for row in rows):
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "模板定额与采纳锁不一致，未按未锁定处理。", 500)
        return {"{}|{}".format(row["part_no"], row["seq"]):
                {"template_operation_ref": row["ref"], "quota_lock": locks.get(row["ref"])} for row in rows}
