"""Read-only lookups binding legacy execution scopes to permanent ledger identities.

Raw values and tuples are returned; the caller decides whether a schema version,
receipt trace or scope binding makes the ledger required, ambiguous or missing.
"""

from __future__ import annotations

from typing import Any, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class ExecutionLedgerScopeRepository(BaseRepository):
    def schema_version_value(self) -> Any:
        """Stored SchemaVersion value as-is, or None without the singleton row."""
        row = self.execute("SELECT version FROM SchemaVersion WHERE id=1").fetchone()
        return None if row is None else row[0]

    def has_execution_command_receipts(self) -> bool:
        row = self.execute("SELECT 1 FROM WorkbenchCommandReceipts WHERE action GLOB 'execution.*' LIMIT 1").fetchone()
        return row is not None

    def scope_task_rows(self, schedule_ids: Sequence[int]) -> List[Tuple[Any, ...]]:
        """(schedule_id, version, op_id, batch_id, operation_ref, task_ref, plan_ref) per adopted schedule row."""
        rows: List[Tuple[Any, ...]] = []
        # Keep the bounded primary-key lookup first on older SQLite planners too.
        for part in chunks(schedule_ids):
            marks = ",".join("?" for _ in part)
            cursor = self.execute(f"""SELECT s.id, s.version, s.op_id, bo.batch_id,
                r.operation_ref, t.ref AS task_ref, p.ref AS plan_ref
                FROM Schedule s CROSS JOIN BatchOperations bo ON bo.id=s.op_id
                CROSS JOIN WorkbenchPlanSourceRefs r ON r.kind='schedule_row' AND r.active=1
                    AND r.source_key=CAST(s.id AS TEXT) AND r.version=s.version AND r.operation_id=s.op_id
                    AND r.source_table='schedule' AND r.owner_key=CAST(s.version AS TEXT)
                CROSS JOIN WorkbenchPlanSourceRefs o ON o.ref=r.operation_ref AND o.kind='operation'
                    AND o.active=1 AND o.source_key=CAST(bo.id AS TEXT)
                CROSS JOIN WorkbenchPlanSourceRefs p ON p.kind='official' AND p.active=1 AND p.version=s.version
                    AND p.source_key=CAST(s.version AS TEXT) AND p.plan_role='adopted' AND p.source_table='schedule'
                JOIN WorkbenchTaskRefs t ON t.row_ref=r.ref AND t.plan_ref=p.ref
                WHERE s.id IN ({marks})""", part)
            rows.extend(tuple(row) for row in cursor)
        return rows

    def reported_operation_without_schedule_row(self) -> Optional[Tuple[Any, ...]]:
        """(source_key,) of one active operation with a live report but no active schedule row, or None."""
        row = self.execute("""SELECT o.source_key FROM WorkbenchPlanSourceRefs o
            WHERE o.kind='operation' AND o.active=1
              AND EXISTS (SELECT 1 FROM WorkbenchProductionReports p WHERE p.operation_ref=o.ref
                  AND NOT EXISTS (SELECT 1 FROM WorkbenchProductionReportVoids v WHERE v.report_ref=p.report_ref))
              AND NOT EXISTS (
                SELECT 1 FROM WorkbenchPlanSourceRefs r JOIN Schedule s
                  ON s.id=CAST(r.source_key AS INTEGER) AND r.source_key=CAST(s.id AS TEXT)
                    AND r.operation_id=s.op_id AND r.version=s.version
                WHERE r.operation_ref=o.ref AND r.kind='schedule_row' AND r.active=1)
            LIMIT 1""").fetchone()
        return None if row is None else tuple(row)
