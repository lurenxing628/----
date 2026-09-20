"""Delivery-owned SELECTs for one resolved plan identity; no admission or binding decisions.

The scenario source keeps its permanent key exactly: the shared plan-rows SQL
helper strips scenario ids, so the scenario parameter is re-supplied verbatim.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.models.schedule_plan_role import SOURCE_ADJUSTMENT_SCENARIO_ROWS

from .schedule_plan_query_repo import SchedulePlanQueryRepository


class WorkbenchPlanDeliveryRepository(SchedulePlanQueryRepository):
    def get_scenario_binding(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT scenario_id, base_version, base_plan_role, base_source_table, "
                             "base_candidate_id, base_candidate_key, status, validation_status, row_count, "
                             "issues_json FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
                             (scenario_id,))

    def _task_query(self, *, version: Any, source_table: str, candidate_id: Optional[int],
                    scenario_id: Optional[str]) -> Tuple[str, List[Any]]:
        sql, extra = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id,
                                         scenario_id=scenario_id)
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            # The legacy SQL helper strips scenario keys; permanent keys are exact.
            extra = [scenario_id]
        return sql, [version] + extra

    def list_task_ids_bounded(self, *, version: Any, source_table: str, candidate_id: Optional[int],
                              scenario_id: Optional[str], limit: int) -> List[Dict[str, Any]]:
        """Plan row ids capped at ``limit``; callers admit the whole plan before any join."""
        sql, params = self._task_query(version=version, source_table=source_table,
                                       candidate_id=candidate_id, scenario_id=scenario_id)
        return self.fetchall("SELECT id FROM (" + sql + ") LIMIT ?", params + [limit])

    def list_task_rows_with_batch(self, *, version: Any, source_table: str, candidate_id: Optional[int],
                                  scenario_id: Optional[str]) -> List[Dict[str, Any]]:
        """Every plan row with its current batch id (NULL when the operation no longer exists)."""
        sql, params = self._task_query(version=version, source_table=source_table,
                                       candidate_id=candidate_id, scenario_id=scenario_id)
        return self.fetchall("WITH plan_rows AS (" + sql + ") SELECT s.id AS schedule_id, s.version, "
                             "s.op_id, CAST(s.start_time AS TEXT) AS start_time, CAST(s.end_time AS TEXT) AS end_time, "
                             "s.machine_id,s.operator_id,bo.batch_id FROM plan_rows s LEFT JOIN BatchOperations bo ON bo.id = s.op_id "
                             "ORDER BY s.id", params)

    def list_batches_by_ids(self, batch_ids: Sequence[str]) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in batch_ids)
        return self.fetchall(
            "SELECT batch_id, part_no, part_name, CAST(due_date AS TEXT) AS due_date FROM Batches "
            "WHERE batch_id IN (" + marks + ") ORDER BY batch_id COLLATE BINARY", list(batch_ids),
        )

    def list_batch_operations_by_ids(self, batch_ids: Sequence[str], *, limit: int) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in batch_ids)
        return self.fetchall(
            "SELECT id AS op_id, batch_id, seq, piece_id FROM BatchOperations WHERE batch_id IN (" + marks +
            ") ORDER BY batch_id COLLATE BINARY, id LIMIT ?", list(batch_ids) + [limit],
        )

    def get_candidate_summary(self, version: Any, candidate_id: Any) -> Optional[Dict[str, Any]]:
        return self.fetchone("SELECT summary_json FROM ScheduleCandidate WHERE version = ? AND id = ?",
                             (version, candidate_id))
