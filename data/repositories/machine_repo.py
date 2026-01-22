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

    def exists(self, machine_id: str) -> bool:
        return bool(self.fetchvalue("SELECT 1 FROM Machines WHERE machine_id = ? LIMIT 1", (machine_id,)))

    def create(self, machine: Union[Machine, Dict[str, Any]]) -> Machine:
        m = machine if isinstance(machine, Machine) else Machine.from_row(machine)
        self.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, status, remark) VALUES (?, ?, ?, ?, ?)",
            (m.machine_id, m.name, m.op_type_id, m.status, m.remark),
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

        allowed = {"name", "op_type_id", "status", "remark"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "op_type_id", "status", "remark"):
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

