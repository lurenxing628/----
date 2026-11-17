"""报工校验只读事实：实体编号连设备能做的工种、完整批次路线、引用了某报工的定额采用记录。

只返回行，上限判断（LIMIT 10001 后的 >10000）归调用方服务。
"""

from __future__ import annotations

import json
from typing import Any, Collection, Dict, List

from .base_repo import BaseRepository
from .machine_capability_repo import MachineCapabilityRepository


class WorkbenchReportValidationRepository(BaseRepository):
    def entity_rows_with_machine_type(self, refs: Collection[str]) -> List[Dict[str, Any]]:
        """读取这些 ref 的实体行，设备行附带它能做的全部工种 op_type_ids（MachineOpTypes）。"""
        if not refs:
            return []
        result = self.fetchall(
            "SELECT * FROM WorkbenchEntityRefs WHERE ref IN (SELECT value FROM json_each(?))",
            (json.dumps(list(refs)),),
        )
        capabilities = MachineCapabilityRepository(self.conn).by_machines(
            [row["entity_key"] for row in result if row["kind"] == "machine"])
        for row in result:
            row["op_type_ids"] = capabilities[row["entity_key"]] if row["kind"] == "machine" else []
        return result

    def batch_operation_rows(self, batch_id: str) -> List[Dict[str, Any]]:
        """Complete batch route with explicit identity gaps; the service resolves dependencies."""
        return self.fetchall("""SELECT bo.*,b.quantity AS batch_quantity,b.part_no,o.ref AS operation_ref
            FROM BatchOperations bo JOIN Batches b ON b.batch_id=bo.batch_id
            LEFT JOIN WorkbenchPlanSourceRefs o ON o.kind='operation' AND o.active=1 AND o.source_key=CAST(bo.id AS TEXT)
            WHERE bo.batch_id=? ORDER BY bo.seq,bo.id LIMIT 10001""", (batch_id,))

    def calibration_adoptions_mentioning(self, report_ref: str) -> List[Dict[str, Any]]:
        """evidence_json 里出现过该报工编号的定额采用记录（最多 10001 行）。"""
        return self.fetchall("""SELECT adoption_ref, template_operation_ref, evidence_json
        FROM WorkbenchCalibrationAdoptions WHERE instr(evidence_json,?)>0 ORDER BY adoption_ref LIMIT 10001""", (report_ref,))
