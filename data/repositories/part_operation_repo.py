from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

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

    def clear_external_group(self, part_no: str, group_id: str) -> int:
        """把某外协组下的工序全部解绑（ext_group_id 置 NULL）。"""
        cursor = self.execute(
            "UPDATE PartOperations SET ext_group_id=NULL WHERE part_no=? AND ext_group_id=?",
            (part_no, group_id),
        )
        return int(cursor.rowcount)

    def mark_deleted_by_id(self, op_id: int) -> int:
        cursor = self.execute("UPDATE PartOperations SET status='deleted' WHERE id=?", (int(op_id),))
        return int(cursor.rowcount)

    def restore_with_op_type_name(self, op_id: int, op_type_name: str) -> int:
        cursor = self.execute(
            "UPDATE PartOperations SET op_type_name=?, status='active' WHERE id=?",
            (op_type_name, int(op_id)),
        )
        return int(cursor.rowcount)

    def insert_route_operation(
        self,
        *,
        part_no: str,
        seq: int,
        op_type_name: str,
        source: Any,
        op_type_id: Any,
        supplier_id: Any,
        ext_days: Any,
    ) -> None:
        """路线确认新增的工序行：工时留空、状态 active。"""
        self.execute(
            """INSERT INTO PartOperations(part_no,seq,op_type_name,source,op_type_id,
            supplier_id,ext_days,setup_hours,unit_hours,status)
            VALUES (?,?,?,?,?,?,?,NULL,NULL,'active')""",
            (part_no, seq, op_type_name, source, op_type_id, supplier_id, ext_days),
        )

    def update_sources_by_id(self, changes: Sequence[Tuple[Any, Any, Any, int]]) -> None:
        """批量写回 (source, op_type_id, supplier_id, id)。"""
        self.executemany("UPDATE PartOperations SET source=?,op_type_id=?,supplier_id=? WHERE id=?", list(changes))

    def update_fields_by_id(self, op_id: int, fields: Dict[str, Any]) -> int:
        """按 id 更新白名单列；列名不在白名单直接抛错，不静默跳过。"""
        allowed = ("setup_hours", "unit_hours", "ext_days", "source", "op_type_id", "supplier_id", "status", "op_type_name")
        unknown = [key for key in fields if key not in allowed]
        if unknown:
            raise ValueError(f"PartOperations 不允许按 id 更新的列：{unknown}")
        if not fields:
            return 0
        assignments = ",".join(name + "=?" for name in fields)
        cursor = self.execute(
            "UPDATE PartOperations SET " + assignments + " WHERE id=?",
            list(fields.values()) + [int(op_id)],
        )
        return int(cursor.rowcount)

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

