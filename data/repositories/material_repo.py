from __future__ import annotations

from typing import Any, Dict

from core.models.material import Material

from .base_repo import BaseRepository


class MaterialRepository(BaseRepository):
    """物料仓库（Materials）。"""

    def create(self, material: Material) -> Material:
        self.execute(
            "INSERT INTO Materials (material_id, name, spec, unit, stock_qty, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                material.material_id,
                material.name,
                material.spec,
                material.unit,
                material.stock_qty,
                material.status,
                material.remark,
            ),
        )
        return material

    def update(self, material_id: str, updates: Dict[str, Any]) -> None:
        params = list(updates.values()) + [material_id]
        set_parts = [f"{k} = ?" for k in updates]
        sql = f"UPDATE Materials SET {', '.join(set_parts)} WHERE material_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (material_id,))
