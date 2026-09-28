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
            "message": "这道工序的单件工时已锁定（来自工时校准），本行跳过，没有导入。锁定只认原来那道模板工序，删掉后重新加的同号工序不算。"}


def quota_skip_summary(rows):
    skipped = [{"row": row["row"], **row["skip_reason"]} for row in rows if row["result"] == "skipped"]
    return {"skipped_count": len(skipped), "skipped_refs": [row["template_operation_ref"] for row in skipped],
            "skipped_rows": skipped}


def require_adoption_schema(repo):
    if not repo.schema_installed():
        raise WorkbenchCommandRejected("adoption_schema_unavailable", "保存采用结果的数据表还没安装或不完整，系统没有自动补表，这次操作没有执行。请先完成统一版本升级后重试。", 503)


def read_quota_locks(repo, template_operation_refs):
    """Return {permanent_ref: lock}; absent key means unlocked only with valid DDL.

    Ordinary writes/imports must call inside their own write transaction. Missing or
    partial DDL and damaged audit pairs are errors even for an empty ref set.
    """
    require_adoption_schema(repo)
    if isinstance(template_operation_refs, (str, bytes)):
        raise WorkbenchCommandRejected(
            "invalid_input",
            "查询定额锁定状态时必须提供一组模板工序，不能只传一条文字值。这次没有查询。",
            400,
        )
    refs = sorted({public_ref(ref) for ref in template_operation_refs})
    if len(refs) > MAX_TEMPLATES:
        raise WorkbenchCommandRejected("query_too_large", "一次最多查 10000 道模板工序的定额锁定状态，这次超了，系统没有截断处理。请缩小范围后重试。", 413)
    result = {}
    for audited, rows in repo.lock_pairs(refs):
        if audited != {row["template_operation_ref"] for row in rows}:
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "采用记录和定额锁定记录对不上，系统没有把它当作未锁定，这次操作没有执行。请联系维护人员。", 500)
        for row in rows:
            if (row["audit_template_ref"] != row["template_operation_ref"] or row["new_unit_hours"] != row["locked_unit_hours"]
                    or row["adopted_at"] != row["locked_at"]):
                raise WorkbenchCommandRejected("calibration_lock_corrupt", "定额锁定的内容和采用记录不一致，系统没有把它当作未锁定，这次操作没有执行。请联系维护人员。", 500)
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
            raise WorkbenchCommandRejected("entity_not_found", "这道模板工序的记录已失效或找不到了，系统不会拿同图号同序号的新工序顶替。请刷新后重新选择。", 404)
        return row["ref"]

    def current(self, refs):
        refs = sorted(set(refs))
        locks = self.read_locks(refs)
        result = {row["ref"]: row for row in self.repo.template_operations_by_refs(refs)}
        if set(result) != set(refs):
            raise WorkbenchCommandRejected("stale_write", "原来的模板工序已失效，系统没有换成同图号同序号的新模板工序，这次没有保存。请刷新后重新操作。")
        for ref, lock in locks.items():
            if result[ref]["unit_hours"] != lock["locked_unit_hours"]:
                raise WorkbenchCommandRejected("calibration_lock_corrupt", "模板的单件工时和已锁定的定额（来自工时校准）不一致，系统没有把它当作未锁定，这次操作没有执行。请联系维护人员。", 500)
        return result, locks

    def require_changes(self, values):
        """Validate proposed unit_hours against live rows, not a caller's old snapshot."""
        if not self.conn.in_transaction:
            raise RuntimeError("普通定额保存必须在调用方写事务中重核。")
        return self.check_changes(values)

    def check_changes(self, values):
        """Read-only preview of the same live quota checks; writes still require_changes."""
        current, locks = self.current(values)
        if any(ref in locks and value != current[ref]["unit_hours"] for ref, value in values.items()):
            raise WorkbenchCommandRejected("calibration_quota_locked", "这道工序的单件工时已锁定（来自工时校准），普通保存不能覆盖，这次没有保存。锁定后这个模板的单件工时不能再改。")
        return current

    def legacy_metadata(self):
        rows = self.repo.legacy_template_operations()
        locks = self.read_locks([row["ref"] for row in rows if row["ref"] is not None])
        if any(row["ref"] is None for row in rows):
            raise WorkbenchCommandRejected("storage_failure", "有模板工序缺少记录，系统没有按图号和序号猜着匹配，这次工时没有导入。请联系维护人员。", 500)
        if any(row["ref"] in locks and row["unit_hours"] != locks[row["ref"]]["locked_unit_hours"] for row in rows):
            raise WorkbenchCommandRejected("calibration_lock_corrupt", "模板的单件工时和已锁定的定额（来自工时校准）不一致，系统没有把它当作未锁定，这次操作没有执行。请联系维护人员。", 500)
        return {"{}|{}".format(row["part_no"], row["seq"]):
                {"template_operation_ref": row["ref"], "quota_lock": locks.get(row["ref"])} for row in rows}
