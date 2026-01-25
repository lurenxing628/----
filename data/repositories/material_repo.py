from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Material

from .base_repo import BaseRepository


class MaterialRepository(BaseRepository):
    """物料仓库（Materials）。"""

    def get(self, material_id: str) -> Optional[Material]:
        row = self.fetchone(
            "SELECT material_id, name, spec, unit, stock_qty, status, remark, created_at FROM Materials WHERE material_id = ?",
            (str(material_id),),
        )
        return Material.from_row(row) if row else None

    def exists(self, material_id: str) -> bool:
        return bool(self.fetchvalue("SELECT 1 FROM Materials WHERE material_id = ? LIMIT 1", (str(material_id),)))

    def list(self, status: Optional[str] = None) -> List[Material]:
        if status:
            rows = self.fetchall(
                "SELECT material_id, name, spec, unit, stock_qty, status, remark, created_at FROM Materials WHERE status = ? ORDER BY material_id",
                (str(status),),
            )
        else:
            rows = self.fetchall(
                "SELECT material_id, name, spec, unit, stock_qty, status, remark, created_at FROM Materials ORDER BY material_id"
            )
        return [Material.from_row(r) for r in rows]

    def create(self, material: Union[Material, Dict[str, Any]]) -> Material:
        m = material if isinstance(material, Material) else Material.from_row(material)
        self.execute(
            "INSERT INTO Materials (material_id, name, spec, unit, stock_qty, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                m.material_id,
                m.name,
                m.spec,
                m.unit,
                float(m.stock_qty or 0.0),
                m.status or "active",
                m.remark,
            ),
        )
        return m

    def update(self, material_id: str, updates: Dict[str, Any]) -> None:
        # stock_qty 允许传空/None 表示不改
        stock_qty = updates.get("stock_qty")
        if stock_qty is not None and str(stock_qty).strip() != "":
            try:
                stock_qty = float(stock_qty)
            except Exception:
                # 留给服务层校验；这里保持原值
                stock_qty = updates.get("stock_qty")
        else:
            stock_qty = None

        self.execute(
            """
            UPDATE Materials
            SET
              name = COALESCE(?, name),
              spec = COALESCE(?, spec),
              unit = COALESCE(?, unit),
              stock_qty = COALESCE(?, stock_qty),
              status = COALESCE(?, status),
              remark = COALESCE(?, remark)
            WHERE material_id = ?
            """,
            (
                updates.get("name"),
                updates.get("spec"),
                updates.get("unit"),
                stock_qty,
                updates.get("status"),
                updates.get("remark"),
                str(material_id),
            ),
        )

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (str(material_id),))

