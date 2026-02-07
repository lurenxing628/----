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
        if not updates:
            return

        allowed = {"name", "spec", "unit", "stock_qty", "status", "remark"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "spec", "unit", "stock_qty", "status", "remark"):
            if key not in allowed or key not in updates:
                continue

            val = updates.get(key)
            if key == "stock_qty":
                # stock_qty 允许传空/None 表示“不改”
                if val is None or (isinstance(val, str) and val.strip() == ""):
                    continue
                try:
                    val = float(val)
                except Exception:
                    # 留给服务层校验；这里保持原值
                    val = updates.get("stock_qty")

            set_parts.append(f"{key} = ?")
            params.append(val)

        if not set_parts:
            return

        params.append(str(material_id))
        sql = f"UPDATE Materials SET {', '.join(set_parts)} WHERE material_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (str(material_id),))

