from __future__ import annotations

import math
from typing import Any, Dict

from core.models import Material

from .base_repo import BaseRepository


def _finite_stock_qty(value: Any, material_id: str) -> float:
    message = f"物料“{material_id}”的 Materials.stock_qty 必须是有限数字，当前值：{value!r}"
    try:
        quantity = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(message) from exc
    if not math.isfinite(quantity):
        raise ValueError(message)
    return quantity


class MaterialRepository(BaseRepository):
    """物料仓库（Materials）。"""

    def create(self, material: Material) -> Material:
        quantity = _finite_stock_qty(material.stock_qty, material.material_id)
        self.execute(
            "INSERT INTO Materials (material_id, name, spec, unit, stock_qty, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                material.material_id,
                material.name,
                material.spec,
                material.unit,
                quantity,
                material.status,
                material.remark,
            ),
        )
        return material

    def update(self, material_id: str, updates: Dict[str, Any]) -> None:
        # R40/O28：旁路也须在执行 SQL 前拒绝坏数量，不能仅依赖 float()。
        params = [_finite_stock_qty(v, material_id) if k == "stock_qty" else v for k, v in updates.items()] + [material_id]
        set_parts = [f"{k} = ?" for k in updates]
        sql = f"UPDATE Materials SET {', '.join(set_parts)} WHERE material_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (material_id,))
