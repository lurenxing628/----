"""Latest official plan rows and execution-scope integrity reads behind resource execution facts.

Rows are mapped from cursor descriptions so any connection row factory yields
identical dicts; duplicate and missing-scope judgements stay with the caller.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .base_repo import BaseRepository


class ScheduleExecutionFactsRepository(BaseRepository):
    def latest_plan_rows(self, version: int) -> List[Dict[str, Any]]:
        """Each operation's last official schedule row at or below ``version``, ordered by op_id, id."""
        # The latest version need not contain every batch. Select each operation's
        # last official identity, never candidate/scenario rows or unscoped events.
        cursor = self.execute(
            """
            SELECT s.id AS schedule_id, s.version, s.op_id, bo.batch_id,
                   bo.source, s.start_time, s.end_time
            FROM Schedule s
            LEFT JOIN BatchOperations bo ON bo.id = s.op_id
            JOIN (SELECT op_id, MAX(version) AS version FROM Schedule
                  WHERE version <= ? GROUP BY op_id) latest
              ON latest.op_id = s.op_id AND latest.version = s.version
            ORDER BY s.op_id, s.id
            """,
            (int(version),),
        )
        columns = [item[0] for item in cursor.description]
        return [dict(zip(columns, values)) for values in cursor]

    def has_event_without_plan_identity(self, source_table: str, effective_plan_role: str) -> bool:
        """True when an unscoped official event no longer matches its schedule row or batch operation."""
        invalid = self.execute(
            """
            SELECT e.op_id FROM OperationExecutionEvents e
            LEFT JOIN Schedule s ON s.id = e.schedule_id
            LEFT JOIN BatchOperations bo ON bo.id = e.op_id
            WHERE e.source_table = ? AND e.effective_plan_role = ? AND e.scenario_id IS NULL
              AND (s.id IS NULL OR bo.id IS NULL OR e.schedule_version != s.version
                   OR e.op_id != s.op_id OR e.batch_id != bo.batch_id)
            LIMIT 1
            """,
            (source_table, effective_plan_role),
        ).fetchone()
        return invalid is not None
