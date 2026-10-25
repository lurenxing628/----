from __future__ import annotations

from typing import Any, Dict

from core.models.operator import Operator

from .base_repo import BaseRepository


class OperatorRepository(BaseRepository):
    """人员仓库（Operators）。"""

    def create(self, operator: Operator) -> None:
        self.execute(
            "INSERT INTO Operators (operator_id, name, status, remark, team_id) VALUES (?, ?, ?, ?, ?)",
            (operator.operator_id, operator.name, operator.status, operator.remark, operator.team_id),
        )

    def update(self, operator_id: str, updates: Dict[str, Any]) -> None:
        """
        更新人员信息。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 remark 显式清空为 NULL（updates['remark']=None）
        """
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [*updates.values(), operator_id]
        sql = f"UPDATE Operators SET {', '.join(set_parts)} WHERE operator_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, operator_id: str) -> None:
        self.execute("DELETE FROM Operators WHERE operator_id = ?", (operator_id,))

