from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import OpType

from .base_repo import BaseRepository


class OpTypeRepository(BaseRepository):
    """工种仓库（OpTypes）。"""

    def get(self, op_type_id: str) -> Optional[OpType]:
        row = self.fetchone(
            "SELECT op_type_id, name, category, default_hours, remark, created_at FROM OpTypes WHERE op_type_id = ?",
            (op_type_id,),
        )
        return OpType.from_row(row) if row else None

    def get_by_name(self, name: str) -> Optional[OpType]:
        row = self.fetchone(
            "SELECT op_type_id, name, category, default_hours, remark, created_at FROM OpTypes WHERE name = ?",
            (name,),
        )
        return OpType.from_row(row) if row else None

    def list(self, category: Optional[str] = None) -> List[OpType]:
        if category:
            rows = self.fetchall(
                "SELECT op_type_id, name, category, default_hours, remark, created_at FROM OpTypes WHERE category = ? ORDER BY name",
                (category,),
            )
        else:
            rows = self.fetchall(
                "SELECT op_type_id, name, category, default_hours, remark, created_at FROM OpTypes ORDER BY name"
            )
        return [OpType.from_row(r) for r in rows]

    def create(self, op_type: Union[OpType, Dict[str, Any]]) -> OpType:
        ot = op_type if isinstance(op_type, OpType) else OpType.from_row(op_type)
        self.execute(
            "INSERT INTO OpTypes (op_type_id, name, category, default_hours, remark) VALUES (?, ?, ?, ?, ?)",
            (ot.op_type_id, ot.name, ot.category, ot.default_hours, ot.remark),
        )
        return ot

    def update(self, op_type_id: str, updates: Dict[str, Any]) -> None:
        if not updates:
            return

        allowed = {"name", "category", "default_hours", "remark"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "category", "default_hours", "remark"):
            if key in allowed and key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        params.append(op_type_id)
        sql = f"UPDATE OpTypes SET {', '.join(set_parts)} WHERE op_type_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, op_type_id: str) -> None:
        self.execute("DELETE FROM OpTypes WHERE op_type_id = ?", (op_type_id,))

