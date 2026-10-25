from __future__ import annotations

from typing import Any, Dict

from core.models import OpType

from .base_repo import BaseRepository


class OpTypeRepository(BaseRepository):
    """工种仓库（OpTypes）。"""

    def create(self, op_type: OpType) -> OpType:
        self.execute(
            "INSERT INTO OpTypes (op_type_id, name, category, default_hours, remark) VALUES (?, ?, ?, ?, ?)",
            (op_type.op_type_id, op_type.name, op_type.category, op_type.default_hours, op_type.remark),
        )
        return op_type

    def update(self, op_type_id: str, updates: Dict[str, Any]) -> None:
        set_parts = [f"{k} = ?" for k in updates]
        params = [*updates.values(), op_type_id]
        sql = f"UPDATE OpTypes SET {', '.join(set_parts)} WHERE op_type_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, op_type_id: str) -> None:
        self.execute("DELETE FROM OpTypes WHERE op_type_id = ?", (op_type_id,))

