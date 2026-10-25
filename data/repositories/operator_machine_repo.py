from __future__ import annotations

from typing import Any, Dict, List, Sequence

from .base_repo import BaseRepository


class OperatorMachineRepository(BaseRepository):
    """人员-设备关联仓库（OperatorMachine）。"""

    def exists(self, operator_id: str, machine_id: str) -> bool:
        return bool(
            self.fetchvalue(
                "SELECT 1 FROM OperatorMachine WHERE operator_id = ? AND machine_id = ? LIMIT 1",
                (operator_id, machine_id),
            )
        )

    def list_simple_rows_for_operators(self, operator_ids: Sequence[str]) -> List[Dict[str, Any]]:
        codes = sorted({x for x in operator_ids if x})
        rows: List[Dict[str, Any]] = []
        for offset in range(0, len(codes), 400):
            chunk = codes[offset:offset + 400]
            placeholders = ",".join(["?"] * len(chunk))
            rows.extend(
                self.fetchall(
                    f"""
                    SELECT operator_id, machine_id, skill_level, is_primary
                    FROM OperatorMachine
                    WHERE operator_id IN ({placeholders})
                    ORDER BY operator_id, machine_id
                    """,
                    tuple(chunk),
                )
            )
        return rows

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
