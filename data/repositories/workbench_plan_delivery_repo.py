"""Delivery-owned related facts; the plan context owns captured arrangements."""

from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .schedule_plan_query_repo import SchedulePlanQueryRepository


class WorkbenchPlanDeliveryRepository(SchedulePlanQueryRepository):
    def list_batches_by_ids(self, batch_ids: Sequence[str]) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in batch_ids)
        return self.fetchall(
            "SELECT batch_id, part_no, part_name, quantity, priority, CAST(due_date AS TEXT) AS due_date FROM Batches "
            "WHERE batch_id IN (" + marks + ") ORDER BY batch_id COLLATE BINARY", list(batch_ids),
        )

    def list_batch_operations_by_ids(self, batch_ids: Sequence[str]) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in batch_ids)
        return self.fetchall(
            "SELECT id AS op_id, batch_id, seq, piece_id FROM BatchOperations WHERE batch_id IN (" + marks +
            ") ORDER BY batch_id COLLATE BINARY, id", list(batch_ids),
        )

    def list_operation_batch_ids(self, operation_ids: Sequence[int]) -> List[Dict[str, Any]]:
        marks = ",".join("?" for _ in operation_ids)
        return self.fetchall("SELECT id AS op_id, batch_id FROM BatchOperations WHERE id IN (" + marks + ")", list(operation_ids))
