"""Read-only lookups binding legacy execution scopes to permanent ledger identities.

Raw tuples are returned; the caller decides whether a scope binding is ambiguous or missing.
"""

from __future__ import annotations

import json
from typing import Any, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository


class ExecutionLedgerScopeRepository(BaseRepository):
    def scope_task_rows(self, schedule_ids: Sequence[int]) -> List[Tuple[Any, ...]]:
        """Schedule identity, permanent refs and the operation's actual internal/external source."""
        cursor = self.execute(
            """SELECT s.id, s.version, s.op_id, bo.batch_id,
                s.operation_ref, s.task_ref, h.plan_ref, bo.source,
                s.start_time, s.end_time, s.machine_id, s.operator_id, s.lock_status,
                bo.setup_hours, bo.unit_hours, s.start_us, s.end_us
                FROM Schedule s
                JOIN ScheduleHistory h ON h.version=s.version
                JOIN BatchOperations bo ON bo.id=s.op_id
                JOIN WorkbenchPlanSourceRefs o
                  ON o.ref=s.operation_ref
                 AND o.kind='operation'
                 AND o.active=1
                 AND o.source_key=CAST(bo.id AS TEXT)
                WHERE s.id IN (SELECT value FROM json_each(?))""",
            (json.dumps(list(schedule_ids)),),
        )
        return [tuple(row) for row in cursor]

    def reported_operation_without_schedule_row(self) -> Optional[Tuple[Any, ...]]:
        """(source_key,) of one active operation with a live report but no active schedule row, or None."""
        row = self.execute("""SELECT o.source_key FROM WorkbenchPlanSourceRefs o
            WHERE o.kind='operation' AND o.active=1
              AND EXISTS (SELECT 1 FROM WorkbenchProductionReports p WHERE p.operation_ref=o.ref AND p.voided=0)
              AND NOT EXISTS (
                SELECT 1 FROM Schedule s
                JOIN ScheduleHistory h ON h.version=s.version
                WHERE s.operation_ref=o.ref AND CAST(s.op_id AS TEXT)=o.source_key)
            LIMIT 1""").fetchone()
        return None if row is None else tuple(row)
