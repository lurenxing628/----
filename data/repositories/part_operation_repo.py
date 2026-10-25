from __future__ import annotations

from typing import Any, Dict

from .base_repo import BaseRepository


class PartOperationRepository(BaseRepository):
    """零件工序模板仓库（PartOperations）。"""

    def clear_external_group(self, part_no: str, group_id: str) -> None:
        """把某外协组下的工序全部解绑（ext_group_id 置 NULL）。"""
        self.execute(
            "UPDATE PartOperations SET ext_group_id=NULL WHERE part_no=? AND ext_group_id=?",
            (part_no, group_id),
        )

    def mark_deleted_by_id(self, op_id: int) -> None:
        self.execute("UPDATE PartOperations SET status='deleted' WHERE id=?", (op_id,))

    def restore_with_op_type_name(self, op_id: int, op_type_name: str) -> None:
        self.execute(
            "UPDATE PartOperations SET op_type_name=?, status='active' WHERE id=?",
            (op_type_name, op_id),
        )

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

    def update_fields_by_id(self, op_id: int, fields: Dict[str, Any]) -> None:
        """按 id 更新指定列。"""
        set_parts = [f"{k} = ?" for k in fields]
        self.execute(
            f"UPDATE PartOperations SET {', '.join(set_parts)} WHERE id = ?",
            (*fields.values(), op_id),
        )
