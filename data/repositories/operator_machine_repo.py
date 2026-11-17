from __future__ import annotations

import json
from typing import Any, Dict, List, Sequence

from .base_repo import BaseRepository


class OperatorMachineRepository(BaseRepository):
    """人员-设备关联仓库（OperatorMachine）。"""

    def list_simple_rows_for_operators(self, operator_ids: Sequence[str]) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT operator_id, machine_id, skill_level, is_primary
            FROM OperatorMachine
            WHERE operator_id IN (SELECT value FROM json_each(?))
            ORDER BY operator_id, machine_id
            """,
            (json.dumps(list(operator_ids)),),
        )

    def add(
        self,
        operator_id: str,
        machine_id: str,
        skill_level: str,
        is_primary: str,
    ) -> None:
        self.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            (operator_id, machine_id, skill_level, is_primary),
        )

    def remove(self, operator_id: str, machine_id: str) -> None:
        self.execute(
            "DELETE FROM OperatorMachine WHERE operator_id = ? AND machine_id = ?",
            (operator_id, machine_id),
        )

    def update_fields(self, operator_id: str, machine_id: str, *, skill_level: str, is_primary: str) -> None:
        self.execute(
            """
            UPDATE OperatorMachine
            SET skill_level = ?, is_primary = ?
            WHERE operator_id = ? AND machine_id = ?
            """,
            (skill_level, is_primary, operator_id, machine_id),
        )
