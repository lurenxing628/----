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

    @staticmethod
    def _list_filters(status: Optional[str]) -> tuple:
        """list 与 count 共用的过滤条件，避免两处各写一套导致分页 total 与实际行数漂移。"""
        if status:
            return " WHERE status = ?", [str(status)]
        return "", []

    def list(self, status: Optional[str] = None, limit: Optional[int] = None, offset: Optional[int] = None) -> List[Material]:
        where_sql, params = self._list_filters(status)
        sql = (
            "SELECT material_id, name, spec, unit, stock_qty, status, remark, created_at FROM Materials"
            + where_sql
            + " ORDER BY material_id"
        )
        if limit is not None:
            sql += " LIMIT ? OFFSET ?"
            params.extend([int(limit), int(offset or 0)])
        rows = self.fetchall(sql, tuple(params) if params else None)
        return [Material.from_row(r) for r in rows]

    def count(self, status: Optional[str] = None) -> int:
        where_sql, params = self._list_filters(status)
        sql = "SELECT COUNT(1) FROM Materials" + where_sql
        return int(self.fetchvalue(sql, tuple(params) if params else None, default=0) or 0)

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
                # 我是故意的（R40/O28）：service 层 _norm_float（material_service.update 路径）是第一道
                # 强校验（库存数量必须数字、>=0），本层绝不静默保留坏值；若未来有旁路绕过 service 直调
                # repo，这里让 float() 自然抛 ValueError 即 loud 暴露，而不是把坏值悄悄写进
                # Materials.stock_qty（REAL 列）——灵魂线，禁止改回 except 吞错保原值。
                val = float(val)

            set_parts.append(f"{key} = ?")
            params.append(val)

        if not set_parts:
            return

        params.append(str(material_id))
        sql = f"UPDATE Materials SET {', '.join(set_parts)} WHERE material_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (str(material_id),))
