from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Machine

from .base_repo import BaseRepository


class MachineRepository(BaseRepository):
    """设备仓库（Machines）。"""

    def get(self, machine_id: str) -> Optional[Machine]:
        row = self.fetchone(
            "SELECT machine_id, name, op_type_id, status, remark, created_at, updated_at FROM Machines WHERE machine_id = ?",
            (machine_id,),
        )
        return Machine.from_row(row) if row else None

    def list(self, status: Optional[str] = None, op_type_id: Optional[str] = None) -> List[Machine]:
        sql = "SELECT machine_id, name, op_type_id, status, remark, created_at, updated_at FROM Machines"
        params: List[Any] = []
        where = []
        if status:
            where.append("status = ?")
            params.append(status)
        if op_type_id:
            where.append("op_type_id = ?")
            params.append(op_type_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY machine_id"
        rows = self.fetchall(sql, tuple(params))
        return [Machine.from_row(r) for r in rows]

    def create(self, machine: Union[Machine, Dict[str, Any]]) -> Machine:
        m = machine if isinstance(machine, Machine) else Machine.from_row(machine)
        self.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, status, remark) VALUES (?, ?, ?, ?, ?)",
            (m.machine_id, m.name, m.op_type_id, m.status, m.remark),
        )
        return m

    def update(self, machine_id: str, updates: Dict[str, Any]) -> None:
        self.execute(
            "UPDATE Machines SET name = COALESCE(?, name), op_type_id = COALESCE(?, op_type_id), status = COALESCE(?, status), remark = COALESCE(?, remark), updated_at = CURRENT_TIMESTAMP WHERE machine_id = ?",
            (
                updates.get("name"),
                updates.get("op_type_id"),
                updates.get("status"),
                updates.get("remark"),
                machine_id,
            ),
        )

    def delete(self, machine_id: str) -> None:
        self.execute("DELETE FROM Machines WHERE machine_id = ?", (machine_id,))

