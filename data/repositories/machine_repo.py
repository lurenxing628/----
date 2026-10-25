from __future__ import annotations

from typing import Any, Dict

from core.models.machine import Machine

from .base_repo import BaseRepository


class MachineRepository(BaseRepository):
    """设备仓库（Machines）。"""

    def create(self, machine: Machine) -> None:
        self.execute(
            "INSERT INTO Machines (machine_id, name, op_type_id, category, status, remark, team_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (machine.machine_id, machine.name, machine.op_type_id, machine.category, machine.status, machine.remark, machine.team_id),
        )

    def update(self, machine_id: str, updates: Dict[str, Any]) -> None:
        """
        更新设备信息。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 op_type_id/remark 显式清空为 NULL（updates['op_type_id']=None）
        """
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [*updates.values(), machine_id]
        sql = f"UPDATE Machines SET {', '.join(set_parts)} WHERE machine_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, machine_id: str) -> None:
        self.execute("DELETE FROM Machines WHERE machine_id = ?", (machine_id,))

