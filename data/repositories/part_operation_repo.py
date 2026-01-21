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
        self.execute(
            """
            UPDATE PartOperations
            SET
              op_type_id = COALESCE(?, op_type_id),
              op_type_name = COALESCE(?, op_type_name),
              source = COALESCE(?, source),
              supplier_id = COALESCE(?, supplier_id),
              ext_days = COALESCE(?, ext_days),
              ext_group_id = COALESCE(?, ext_group_id),
              setup_hours = COALESCE(?, setup_hours),
              unit_hours = COALESCE(?, unit_hours),
              status = COALESCE(?, status)
            WHERE part_no = ? AND seq = ?
            """,
            (
                updates.get("op_type_id"),
                updates.get("op_type_name"),
                updates.get("source"),
                updates.get("supplier_id"),
                updates.get("ext_days"),
                updates.get("ext_group_id"),
                updates.get("setup_hours"),
                updates.get("unit_hours"),
                updates.get("status"),
                part_no,
                int(seq),
            ),
        )

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

