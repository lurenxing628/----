"""Current template hours: stable identity, existing revision and caller transaction."""

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.process_query_repo import ProcessQueryRepository
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository


class ProcessTemplateHours:
    def __init__(self, conn):
        self.conn = conn
        self.repo = ProcessQueryRepository(conn)
        self.writer = WorkbenchProcessHoursRepository(conn)

    def bind(self, part_no, seq):
        row = self.repo.template_operation_ref(part_no, seq)
        if row is None or row["ref"] is None:
            raise WorkbenchCommandRejected("entity_not_found", "这道模板工序已失效，请刷新后重新选择。", 404)
        return row["ref"]

    def current(self, refs):
        refs = sorted(set(refs))
        result = {row["ref"]: row for row in self.repo.template_operations_by_refs(refs)}
        if set(result) != set(refs):
            raise WorkbenchCommandRejected("stale_write", "原模板工序已失效，这次没有保存。请刷新后重新操作。")
        return result

    def revise(self, ref, values, *, expected_revision):
        if not self.conn.in_transaction:
            raise RuntimeError("模板工时修订必须在调用方写事务中执行。")
        current = self.current([ref])[ref]
        if current["revision"] != expected_revision:
            raise WorkbenchCommandRejected("stale_write", "模板工序在预检后已变化，请重新核对。")
        changes = {key: value for key, value in values.items() if current[key] != value}
        if changes and self.writer.update_operation_hours(current["id"], changes, ref=ref, revision=expected_revision) != 1:
            raise WorkbenchCommandRejected("stale_write", "模板工序在保存前已变化，请重新核对。")
