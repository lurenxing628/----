"""Delivery-owned related facts; the plan context owns captured arrangements."""

from __future__ import annotations

import json
from typing import Any, Collection, Dict, List, Sequence

from .schedule_plan_query_repo import SchedulePlanQueryRepository


class WorkbenchPlanDeliveryRepository(SchedulePlanQueryRepository):
    def list_batches_by_ids(self, batch_ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not batch_ids:
            return []
        return self.fetchall(
            "SELECT batch_id, part_no, part_name, quantity, priority, +due_date AS due_date FROM Batches "
            "WHERE batch_id IN (SELECT value FROM json_each(?)) ORDER BY batch_id COLLATE BINARY",
            (json.dumps(list(batch_ids)),),
        )

    def list_batch_operations_by_ids(self, batch_ids: Sequence[str]) -> List[Dict[str, Any]]:
        if not batch_ids:
            return []
        return self.fetchall(
            "SELECT id AS op_id, batch_id, seq, piece_id FROM BatchOperations "
            "WHERE batch_id IN (SELECT value FROM json_each(?)) ORDER BY batch_id COLLATE BINARY, id",
            (json.dumps(list(batch_ids)),),
        )

    def list_operation_batch_ids(self, operation_ids: Collection[int]) -> List[Dict[str, Any]]:
        return self.fetchall(
            "SELECT id AS op_id, batch_id FROM BatchOperations WHERE id IN (SELECT value FROM json_each(?))",
            (json.dumps(list(operation_ids)),),
        )
