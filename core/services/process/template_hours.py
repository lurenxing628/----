"""Current template hours: stable identity, existing revision and caller transaction."""

from core.models.workbench_command import WorkbenchCommandRejected
from data.repositories.workbench_process_hours_repo import WorkbenchProcessHoursRepository


class ProcessTemplateHours:
    def __init__(self, conn):
        self.conn = conn
        self.repo = WorkbenchProcessHoursRepository(conn)

    def revise_current(self, current, values, *, expected_revision):
        """Revise a current row already read in the caller's write transaction."""
        if not self.conn.in_transaction:
            raise RuntimeError("模板工时修订必须在调用方写事务中执行。")
        if current["revision"] != expected_revision:
            raise WorkbenchCommandRejected("stale_write", "模板工序在预检后已变化，请重新核对。")
        changes = {key: value for key, value in values.items() if current[key] != value}
        if changes and self.repo.update_operation_hours(
                current["id"], changes, ref=current["ref"], revision=expected_revision) != 1:
            raise WorkbenchCommandRejected("stale_write", "模板工序在保存前已变化，请重新核对。")
