from __future__ import annotations

from typing import List, Optional

from core.models import OperatorMachine

from .base_repo import BaseRepository


class OperatorMachineRepository(BaseRepository):
    """人员-设备关联仓库（OperatorMachine）。"""

    def get(self, link_id: int) -> Optional[OperatorMachine]:
        row = self.fetchone(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE id = ?",
            (link_id,),
        )
        return OperatorMachine.from_row(row) if row else None

    def exists(self, operator_id: str, machine_id: str) -> bool:
        return bool(
            self.fetchvalue(
                "SELECT 1 FROM OperatorMachine WHERE operator_id = ? AND machine_id = ? LIMIT 1",
                (operator_id, machine_id),
            )
        )

    def list_by_operator(self, operator_id: str) -> List[OperatorMachine]:
        rows = self.fetchall(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE operator_id = ? ORDER BY id",
            (operator_id,),
        )
        return [OperatorMachine.from_row(r) for r in rows]

    def list_by_machine(self, machine_id: str) -> List[OperatorMachine]:
        rows = self.fetchall(
            "SELECT id, operator_id, machine_id, skill_level, is_primary, created_at FROM OperatorMachine WHERE machine_id = ? ORDER BY id",
            (machine_id,),
        )
        return [OperatorMachine.from_row(r) for r in rows]

    def add(
        self,
        operator_id: str,
        machine_id: str,
        skill_level: str = "normal",
        is_primary: str = "no",
    ) -> OperatorMachine:
        cur = self.execute(
            "INSERT INTO OperatorMachine (operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
            (operator_id, machine_id, skill_level, is_primary),
        )
        return OperatorMachine(
            id=int(cur.lastrowid) if cur.lastrowid is not None else None,
            operator_id=operator_id,
            machine_id=machine_id,
            skill_level=skill_level,
            is_primary=is_primary,
        )

    def remove(self, operator_id: str, machine_id: str) -> None:
        self.execute(
            "DELETE FROM OperatorMachine WHERE operator_id = ? AND machine_id = ?",
            (operator_id, machine_id),
        )

    def delete(self, link_id: int) -> None:
        self.execute("DELETE FROM OperatorMachine WHERE id = ?", (link_id,))

    def update_fields(self, operator_id: str, machine_id: str, *, skill_level: str, is_primary: str) -> int:
        cur = self.execute(
            """
            UPDATE OperatorMachine
            SET skill_level = ?, is_primary = ?
            WHERE operator_id = ? AND machine_id = ?
            """,
            (skill_level, is_primary, operator_id, machine_id),
        )
        return int(getattr(cur, "rowcount", 0) or 0)

    def clear_primary_for_operator(self, operator_id: str) -> int:
        cur = self.execute("UPDATE OperatorMachine SET is_primary = 'no' WHERE operator_id = ?", (operator_id,))
        return int(getattr(cur, "rowcount", 0) or 0)

