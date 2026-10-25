from __future__ import annotations

from typing import Any, Dict

from core.models import Supplier

from .base_repo import BaseRepository


class SupplierRepository(BaseRepository):
    """供应商仓库（Suppliers）。"""

    def create(self, supplier: Supplier) -> None:
        self.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status, remark) VALUES (?, ?, ?, ?, ?, ?)",
            (supplier.supplier_id, supplier.name, supplier.op_type_id, supplier.default_days, supplier.status, supplier.remark),
        )

    def update(self, supplier_id: str, updates: Dict[str, Any]) -> None:
        """
        更新供应商。

        说明：
        - 只更新 updates 中出现的字段
        - 允许显式清空 op_type_id/remark 为 NULL（便于后续调整绑定关系）
        """
        set_parts = [f"{k} = ?" for k in updates]
        params = [*updates.values(), supplier_id]
        sql = f"UPDATE Suppliers SET {', '.join(set_parts)} WHERE supplier_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, supplier_id: str) -> None:
        self.execute("DELETE FROM Suppliers WHERE supplier_id = ?", (supplier_id,))

