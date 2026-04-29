from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Machine

from .base_repo import BaseRepository
from .reference_checks import exists_any_nonblank_reference, exists_value_reference


class MachineRepository(BaseRepository):
    """设备仓库（Machines）。"""

    def get(self, machine_id: str) -> Optional[Machine]:
        row = self.fetchone(
            "SELECT machine_id, name, op_type_id, category, status, remark, team_id, created_at, updated_at FROM Machines WHERE machine_id = ?",
            (machine_id,),
        )
        return Machine.from_row(row) if row else None

    def list(
        self,
        status: Optional[str] = None,
        op_type_id: Optional[str] = None,
        category: Optional[str] = None,
        team_id: Optional[str] = None,
    ) -> List[Machine]:
        sql = "SELECT machine_id, name, op_type_id, category, status, remark, team_id, created_at, updated_at FROM Machines"
        params: List[Any] = []
        where = []
        if status:
            where.append("status = ?")
            params.append(status)
        if op_type_id:
            where.append("op_type_id = ?")
            params.append(op_type_id)
        if category:
            where.append("category = ?")
            params.append(category)
        if team_id:
            where.append("team_id = ?")
            params.append(team_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY machine_id"
        rows = self.fetchall(sql, tuple(params))
        return [Machine.from_row(r) for r in rows]

    def exists(self, machine_id: str) -> bool:
        return bool(self.fetchvalue("SELECT 1 FROM Machines WHERE machine_id = ? LIMIT 1", (machine_id,)))

    def create(self, machine: Union[Machine, Dict[str, Any]]) -> Machine:
        m = machine if isinstance(machine, Machine) else Machine.from_row(machine)
        self.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, category, status, remark, team_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (m.machine_id, m.name, m.op_type_id, m.category, m.status, m.remark, m.team_id),
        )
        return m

    def update(self, machine_id: str, updates: Dict[str, Any]) -> None:
        """
        更新设备信息。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 op_type_id/remark 显式清空为 NULL（updates['op_type_id']=None）
        """
        if not updates:
            return

        allowed = {"name", "op_type_id", "category", "status", "remark", "team_id"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "op_type_id", "category", "status", "remark", "team_id"):
            if key not in allowed:
                continue
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        params.append(machine_id)

        sql = f"UPDATE Machines SET {', '.join(set_parts)} WHERE machine_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, machine_id: str) -> None:
        self.execute("DELETE FROM Machines WHERE machine_id = ?", (machine_id,))

    def delete_all(self) -> None:
        self.execute("DELETE FROM Machines")

    def is_referenced_by_batch_operations(self, machine_id: str) -> bool:
        return exists_value_reference(
            self,
            table="BatchOperations",
            column="machine_id",
            value=machine_id,
        )

    def is_referenced_by_schedule(self, machine_id: str) -> bool:
        return exists_value_reference(
            self,
            table="Schedule",
            column="machine_id",
            value=machine_id,
        )

    def has_any_batch_operations_machine_reference(self) -> bool:
        return exists_any_nonblank_reference(
            self,
            table="BatchOperations",
            column="machine_id",
        )

    def has_any_schedule_machine_reference(self) -> bool:
        return exists_any_nonblank_reference(
            self,
            table="Schedule",
            column="machine_id",
        )

    def list_for_export(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT
                m.machine_id,
                m.name,
                m.status,
                m.team_id,
                ot.name AS op_type_name,
                rt.name AS team_name
            FROM Machines m
            LEFT JOIN OpTypes ot ON ot.op_type_id = m.op_type_id
            LEFT JOIN ResourceTeams rt ON rt.team_id = m.team_id
            ORDER BY m.machine_id
            """
        )
