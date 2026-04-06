from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Supplier

from .base_repo import BaseRepository


class SupplierRepository(BaseRepository):
    """供应商仓库（Suppliers）。"""

    def get(self, supplier_id: str) -> Optional[Supplier]:
        row = self.fetchone(
            "SELECT supplier_id, name, op_type_id, default_days, status, remark, created_at FROM Suppliers WHERE supplier_id = ?",
            (supplier_id,),
        )
        return Supplier.from_row(row) if row else None

    def list(self, status: Optional[str] = None, op_type_id: Optional[str] = None) -> List[Supplier]:
        sql = "SELECT supplier_id, name, op_type_id, default_days, status, remark, created_at FROM Suppliers"
        params: List[Any] = []
        where = []
        if status:
            where.append("status = ?")
            params.append(status)
        if op_type_id:
            where.append("op_type_id = ?")
            params.append(op_type_id)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY supplier_id"
        rows = self.fetchall(sql, tuple(params))
        return [Supplier.from_row(r) for r in rows]

    def create(self, supplier: Union[Supplier, Dict[str, Any]]) -> Supplier:
        s = supplier if isinstance(supplier, Supplier) else Supplier.from_row(supplier)
        self.execute(
            "INSERT INTO Suppliers (supplier_id, name, op_type_id, default_days, status, remark) VALUES (?, ?, ?, ?, ?, ?)",
            (s.supplier_id, s.name, s.op_type_id, s.default_days, s.status, s.remark),
        )
        return s

    def update(self, supplier_id: str, updates: Dict[str, Any]) -> None:
        """
        更新供应商。

        说明：
        - 只更新 updates 中出现的字段
        - 允许显式清空 op_type_id/remark 为 NULL（便于后续调整绑定关系）
        """
        if not updates:
            return

        allowed = {"name", "op_type_id", "default_days", "status", "remark"}
        set_parts: List[str] = []
        params: List[Any] = []

        for key in ("name", "op_type_id", "default_days", "status", "remark"):
            if key not in allowed:
                continue
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        # 兼容：部分库/旧 schema 可能没有 updated_at；存在则更新（最佳努力）
        cols = self.fetchall("PRAGMA table_info(Suppliers)")
        if any(str(r.get("name")) == "updated_at" for r in (cols or [])):
            set_parts.append("updated_at = CURRENT_TIMESTAMP")

        params.append(supplier_id)
        sql = f"UPDATE Suppliers SET {', '.join(set_parts)} WHERE supplier_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, supplier_id: str) -> None:
        self.execute("DELETE FROM Suppliers WHERE supplier_id = ?", (supplier_id,))

    def delete_all(self) -> None:
        self.execute("DELETE FROM Suppliers")

    def list_for_export(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT s.supplier_id, s.name, s.default_days, s.status, s.remark, ot.name AS op_type_name
            FROM Suppliers s
            LEFT JOIN OpTypes ot ON ot.op_type_id = s.op_type_id
            ORDER BY s.supplier_id
            """
        )

    # -------------------------
    # 引用检查（给 Service 层做删除/清空保护）
    # -------------------------
    def has_part_operation_reference(self, supplier_id: str) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM PartOperations WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' AND supplier_id = ? LIMIT 1",
                (supplier_id,),
                default=None,
            )
            is not None
        )

    def has_batch_operation_reference(self, supplier_id: str) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM BatchOperations WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' AND supplier_id = ? LIMIT 1",
                (supplier_id,),
                default=None,
            )
            is not None
        )

    def has_external_group_reference(self, supplier_id: str) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM ExternalGroups WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' AND supplier_id = ? LIMIT 1",
                (supplier_id,),
                default=None,
            )
            is not None
        )

    def has_any_part_operation_reference(self) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM PartOperations WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' LIMIT 1",
                default=None,
            )
            is not None
        )

    def has_any_batch_operation_reference(self) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM BatchOperations WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' LIMIT 1",
                default=None,
            )
            is not None
        )

    def has_any_external_group_reference(self) -> bool:
        return (
            self.fetchvalue(
                "SELECT 1 FROM ExternalGroups WHERE supplier_id IS NOT NULL AND TRIM(supplier_id) <> '' LIMIT 1",
                default=None,
            )
            is not None
        )

