from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Operator

from .base_repo import BaseRepository


class OperatorRepository(BaseRepository):
    """人员仓库（Operators）。"""

    def get(self, operator_id: str) -> Optional[Operator]:
        row = self.fetchone(
            "SELECT operator_id, name, status, remark, team_id, created_at, updated_at FROM Operators WHERE operator_id = ?",
            (operator_id,),
        )
        return Operator.from_row(row) if row else None

    def list(self, status: Optional[str] = None, team_id: Optional[str] = None) -> List[Operator]:
        sql = "SELECT operator_id, name, status, remark, team_id, created_at, updated_at FROM Operators"
        params: List[Any] = []
        where: List[str] = []
        if status:
            where.append("status = ?")
            params.append(status)
        if team_id:
            where.append("team_id = ?")
            params.append(team_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY operator_id"
        rows = self.fetchall(sql, tuple(params))
        return [Operator.from_row(r) for r in rows]

    def exists(self, operator_id: str) -> bool:
        return bool(self.fetchvalue("SELECT 1 FROM Operators WHERE operator_id = ? LIMIT 1", (operator_id,)))

    def create(self, operator: Union[Operator, Dict[str, Any]]) -> Operator:
        op = operator if isinstance(operator, Operator) else Operator.from_row(operator)
        self.execute(
            "INSERT INTO Operators (operator_id, name, status, remark, team_id) VALUES (?, ?, ?, ?, ?)",
            (op.operator_id, op.name, op.status, op.remark, op.team_id),
        )
        return op

    def update(self, operator_id: str, updates: Dict[str, Any]) -> None:
        """
        更新人员信息。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 remark 显式清空为 NULL（updates['remark']=None）
        """
        if not updates:
            return

        allowed = {"name", "status", "remark", "team_id"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "status", "remark", "team_id"):
            if key not in allowed:
                continue
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        set_parts.append("updated_at = CURRENT_TIMESTAMP")
        params.append(operator_id)

        sql = f"UPDATE Operators SET {', '.join(set_parts)} WHERE operator_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, operator_id: str) -> None:
        self.execute("DELETE FROM Operators WHERE operator_id = ?", (operator_id,))

    def delete_all(self) -> None:
        self.execute("DELETE FROM Operators")

    def list_as_dicts(self) -> List[Dict[str, Any]]:
        return self.fetchall("SELECT operator_id, name, status, remark, team_id FROM Operators ORDER BY operator_id")

    # -------------------------
    # 引用检查（给 Service 层做删除/清空保护）
    # -------------------------
    def is_referenced_by_batch_operations(self, operator_id: str) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM BatchOperations WHERE operator_id = ? LIMIT 1",
                (operator_id,),
                default=None,
            )
            is not None
        )

    def is_referenced_by_schedule(self, operator_id: str) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM Schedule WHERE operator_id = ? LIMIT 1",
                (operator_id,),
                default=None,
            )
            is not None
        )

    def has_any_batch_operations_operator_reference(self) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM BatchOperations WHERE operator_id IS NOT NULL AND TRIM(operator_id) <> '' LIMIT 1",
                default=None,
            )
            is not None
        )

    def has_any_schedule_operator_reference(self) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM Schedule WHERE operator_id IS NOT NULL AND TRIM(operator_id) <> '' LIMIT 1",
                default=None,
            )
            is not None
        )
