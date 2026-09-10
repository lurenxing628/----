from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Union

from core.infrastructure.errors import AppError, ErrorCode
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


def _material_from_row(row: Dict[str, Any]) -> Material:
    try:
        return Material.from_row(row)
    except ValueError as exc:
        material_id = str(row.get("material_id") or "")
        value = repr(row.get("stock_qty"))
        details = {"table": "Materials", "material_id": material_id, "field": "stock_qty", "value": value}
        raise AppError(
            ErrorCode.DB_INTEGRITY_ERROR,
            f"物料“{material_id}”库存数量不是有效的有限数字，无法读取，请核对原始数据。",
            details=details,
            internal_details=details,
            cause=exc,
        ) from exc


class MaterialRepository(BaseRepository):
    """物料仓库（Materials）。"""

    def get(self, material_id: str) -> Optional[Material]:
        row = self.fetchone(
            "SELECT material_id, name, spec, unit, stock_qty, status, remark, created_at FROM Materials WHERE material_id = ?",
            (str(material_id),),
        )
        return _material_from_row(row) if row else None

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
        return [_material_from_row(r) for r in rows]

    def count(self, status: Optional[str] = None) -> int:
        where_sql, params = self._list_filters(status)
        sql = "SELECT COUNT(1) FROM Materials" + where_sql
        return int(self.fetchvalue(sql, tuple(params) if params else None, default=0) or 0)

    def create(self, material: Union[Material, Dict[str, Any]]) -> Material:
        m = material if isinstance(material, Material) else Material.from_row(material)
        quantity = _finite_stock_qty(m.stock_qty or 0.0, m.material_id)
        self.execute(
            "INSERT INTO Materials (material_id, name, spec, unit, stock_qty, status, remark) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                m.material_id,
                m.name,
                m.spec,
                m.unit,
                quantity,
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
                # R40/O28：旁路也须在执行 SQL 前拒绝坏数量，不能仅依赖 float()。
                val = _finite_stock_qty(val, str(material_id))

            set_parts.append(f"{key} = ?")
            params.append(val)

        if not set_parts:
            return

        params.append(str(material_id))
        sql = f"UPDATE Materials SET {', '.join(set_parts)} WHERE material_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, material_id: str) -> None:
        self.execute("DELETE FROM Materials WHERE material_id = ?", (str(material_id),))
