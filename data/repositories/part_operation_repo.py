from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import PartOperation

from .base_repo import BaseRepository


class PartOperationRepository(BaseRepository):
    """零件工序模板仓库（PartOperations）。"""

    def get(self, part_no: str, seq: int) -> Optional[PartOperation]:
        row = self.fetchone(
            "SELECT id, part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status, created_at FROM PartOperations WHERE part_no = ? AND seq = ?",
            (part_no, int(seq)),
        )
        return PartOperation.from_row(row) if row else None

    def list_by_part(self, part_no: str, include_deleted: bool = False) -> List[PartOperation]:
        if include_deleted:
            rows = self.fetchall(
                "SELECT id, part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status, created_at FROM PartOperations WHERE part_no = ? ORDER BY seq",
                (part_no,),
            )
        else:
            rows = self.fetchall(
                "SELECT id, part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status, created_at FROM PartOperations WHERE part_no = ? AND status = 'active' ORDER BY seq",
                (part_no,),
            )
        return [PartOperation.from_row(r) for r in rows]

    def list_all_active_with_details(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT
              p.part_no,
              po.seq,
              po.op_type_name,
              po.source,
              po.supplier_id,
              s.name AS supplier_name,
              po.ext_days,
              po.ext_group_id,
              eg.merge_mode,
              eg.total_days
            FROM PartOperations po
            JOIN Parts p ON p.part_no = po.part_no
            LEFT JOIN Suppliers s ON s.supplier_id = po.supplier_id
            LEFT JOIN ExternalGroups eg ON eg.group_id = po.ext_group_id
            WHERE po.status = 'active'
            ORDER BY p.part_no, po.seq
            """
        )

    def list_active_hours(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT part_no, seq, op_type_name, source, setup_hours, unit_hours
            FROM PartOperations
            WHERE status='active'
            ORDER BY part_no, seq
            """
        )

    def list_internal_active_hours(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT part_no, seq, setup_hours, unit_hours
            FROM PartOperations
            WHERE status='active' AND source='internal'
            ORDER BY part_no, seq
            """
        )

    def create(self, op: Union[PartOperation, Dict[str, Any]]) -> PartOperation:
        po = op if isinstance(op, PartOperation) else PartOperation.from_row(op)
        cur = self.execute(
            """
            INSERT INTO PartOperations
            (part_no, seq, op_type_id, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                po.part_no,
                int(po.seq),
                po.op_type_id,
                po.op_type_name,
                po.source,
                po.supplier_id,
                po.ext_days,
                po.ext_group_id,
                po.setup_hours,
                po.unit_hours,
                po.status,
            ),
        )
        po.id = int(cur.lastrowid) if cur.lastrowid is not None else po.id
        return po

    def update(self, part_no: str, seq: int, updates: Dict[str, Any]) -> None:
        """
        更新零件工序模板。

        说明：
        - 只更新 updates 中出现的字段
        - 允许显式清空字段为 NULL（例如 ext_days/ext_group_id/supplier_id）
          这是实现 external group 的 separate/merged 存储规则所必需的。
        """
        if not updates:
            return

        allowed = {
            "op_type_id",
            "op_type_name",
            "source",
            "supplier_id",
            "ext_days",
            "ext_group_id",
            "setup_hours",
            "unit_hours",
            "status",
        }
        set_parts: List[str] = []
        params: List[Any] = []

        for key in (
            "op_type_id",
            "op_type_name",
            "source",
            "supplier_id",
            "ext_days",
            "ext_group_id",
            "setup_hours",
            "unit_hours",
            "status",
        ):
            if key not in allowed:
                continue
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        params.extend([part_no, int(seq)])
        sql = f"UPDATE PartOperations SET {', '.join(set_parts)} WHERE part_no = ? AND seq = ?"
        self.execute(sql, tuple(params))

    def mark_deleted(self, part_no: str, seq: int) -> None:
        """逻辑删除：status=deleted（符合文档“active/deleted”）。"""
        self.execute(
            "UPDATE PartOperations SET status = 'deleted' WHERE part_no = ? AND seq = ?",
            (part_no, int(seq)),
        )

    def delete(self, op_id: int) -> None:
        """物理删除（谨慎使用）。"""
        self.execute("DELETE FROM PartOperations WHERE id = ?", (int(op_id),))

    def delete_by_part(self, part_no: str) -> None:
        self.execute("DELETE FROM PartOperations WHERE part_no = ?", (part_no,))

