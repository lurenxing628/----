"""报工校验只读事实：实体编号连设备工种、同批次后续工序、引用了某报工的定额采用记录。

只返回行，上限判断（LIMIT 10001 后的 >10000）归调用方服务。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .base_repo import BaseRepository
from .workbench_execution_repo import chunks


class WorkbenchReportValidationRepository(BaseRepository):
    def entity_rows_with_machine_type(self, refs: Iterable[str]) -> List[Dict[str, Any]]:
        """按 ref 去重排序后分批读实体行，设备行附带 machine_type（op_type_id）。"""
        result: List[Dict[str, Any]] = []
        for chunk in chunks(sorted(set(refs))):
            marks = ",".join("?" for _ in chunk)
            result.extend(self.fetchall(f"""SELECT e.*, m.op_type_id AS machine_type FROM WorkbenchEntityRefs e
                LEFT JOIN Machines m ON e.kind='machine' AND e.active=1 AND m.machine_id=e.entity_key
                WHERE e.ref IN ({marks})""", chunk))
        return result

    def successor_operation_rows(self, batch_id: str, piece_id: Optional[str], seq: int) -> List[Dict[str, Any]]:
        """同批次同件、序号更大的工序（最多 10001 行，seq 升序）。"""
        return self.fetchall("""SELECT bo.id, bo.status, o.ref AS operation_ref FROM BatchOperations bo
        JOIN WorkbenchPlanSourceRefs o ON o.kind='operation' AND o.active=1 AND o.source_key=CAST(bo.id AS TEXT)
        WHERE bo.batch_id=? AND bo.piece_id IS ? AND bo.seq>? ORDER BY bo.seq LIMIT 10001""",
            (batch_id, piece_id, seq))

    def calibration_adoptions_mentioning(self, report_ref: str) -> List[Dict[str, Any]]:
        """evidence_json 里出现过该报工编号的定额采用记录（最多 10001 行）。"""
        return self.fetchall("""SELECT adoption_ref, template_operation_ref, evidence_json
        FROM WorkbenchCalibrationAdoptions WHERE instr(evidence_json,?)>0 ORDER BY adoption_ref LIMIT 10001""", (report_ref,))
