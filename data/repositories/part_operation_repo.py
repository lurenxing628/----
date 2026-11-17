from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository

_CONFIRMATION_OP_SQL = """SELECT o.*, t.name AS type_name, t.category
    FROM PartOperations o
    LEFT JOIN OpTypes t ON t.op_type_id=o.op_type_id
    WHERE o.status='active'"""

_SUPPLIER_BASE_WHERE = """status='active' AND source='external' AND (
    supplier_id=?
    OR EXISTS (
        SELECT 1 FROM ExternalGroups g
        WHERE g.group_id=PartOperations.ext_group_id
          AND g.merge_mode='merged'
          AND g.supplier_id=?
    )
)"""


class PartOperationRepository(BaseRepository):
    """零件工序模板仓库（PartOperations）及关联工艺确认读写。"""

    def _dict_rows(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self.execute(sql, params)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor]

    def active_operations_with_policies(self, part_no: str) -> List[Dict[str, Any]]:
        return self._dict_rows(
            """SELECT o.*, t.category, p.default_merge_mode
               FROM PartOperations o
               LEFT JOIN OpTypes t ON t.op_type_id=o.op_type_id
               LEFT JOIN WorkbenchOpTypePolicies p ON p.op_type_id=t.op_type_id
               WHERE o.status='active' AND o.part_no=?
               ORDER BY o.seq, o.id""",
            (part_no,),
        )

    def active_confirmation_operations(self, part_no: str) -> List[Dict[str, Any]]:
        return self._dict_rows(
            _CONFIRMATION_OP_SQL + " AND o.part_no=? ORDER BY o.seq, o.id",
            (part_no,),
        )

    def part_external_group_ids(self, part_no: str) -> List[str]:
        return [
            str(row[0])
            for row in self.execute("SELECT group_id FROM ExternalGroups WHERE part_no=?", (part_no,)).fetchall()
        ]

    def external_groups_by_ids(self, group_ids_json: str) -> List[Dict[str, Any]]:
        return self._dict_rows(
            "SELECT * FROM ExternalGroups WHERE group_id IN (SELECT value FROM json_each(?))",
            (group_ids_json,),
        )

    def cross_part_group_operations(self, part_no: str, group_ids_json: str) -> List[Dict[str, Any]]:
        return self._dict_rows(
            _CONFIRMATION_OP_SQL + " AND o.part_no<>? AND o.ext_group_id IN (SELECT value FROM json_each(?))",
            (part_no, group_ids_json),
        )

    def supplier_confirmation_catalog(
        self, supplier_ids_json: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        suppliers = self._dict_rows(
            """SELECT s.supplier_id, s.status, p.inactive_reason
               FROM Suppliers s
               LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id
               WHERE s.supplier_id IN (SELECT value FROM json_each(?))""",
            (supplier_ids_json,),
        )
        capabilities = self._dict_rows(
            "SELECT supplier_id, op_type_id FROM WorkbenchSupplierOpTypes "
            "WHERE supplier_id IN (SELECT value FROM json_each(?))",
            (supplier_ids_json,),
        )
        return suppliers, capabilities

    def clear_external_group(self, part_no: str, group_id: str) -> None:
        """把某外协组下的工序全部解绑（ext_group_id 置 NULL），并同步清空工序归属与工时确认。"""
        self.execute(
            "UPDATE PartOperations SET ext_group_id=NULL, source_confirmed_at=NULL, hours_confirmed_at=NULL "
            "WHERE part_no=? AND ext_group_id=?",
            (part_no, group_id),
        )

    def mark_deleted_by_id(self, op_id: int) -> None:
        self.execute(
            "UPDATE PartOperations SET status='deleted', source_confirmed_at=NULL, hours_confirmed_at=NULL WHERE id=?",
            (op_id,),
        )

    def restore_with_op_type_name(self, op_id: int, op_type_name: str) -> None:
        self.execute(
            "UPDATE PartOperations SET op_type_name=?, status='active', source_confirmed_at=NULL, hours_confirmed_at=NULL WHERE id=?",
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

    def set_stage_confirmed_at(self, part_no: str, stage: str, stamp: str) -> None:
        if stage == "source":
            self.execute(
                "UPDATE PartOperations SET source_confirmed_at=? "
                "WHERE part_no=? AND status='active' AND source_confirmed_at IS NULL",
                (stamp, part_no),
            )
        elif stage == "hours":
            self.execute(
                "UPDATE PartOperations SET hours_confirmed_at=? "
                "WHERE part_no=? AND status='active' AND hours_confirmed_at IS NULL",
                (stamp, part_no),
            )
        else:
            raise ValueError(f"Unsupported operation stage: {stage}")

    def reset_confirmations_by_ids(self, ids_json: str) -> None:
        """清空这些工序的归属与工时确认。"""
        self.execute(
            """UPDATE PartOperations
               SET source_confirmed_at=NULL, hours_confirmed_at=NULL
               WHERE id IN (SELECT value FROM json_each(?))
                 AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)""",
            (ids_json,),
        )

    def reset_group_hours_confirmations(self, groups_json: str) -> None:
        self.execute(
            """UPDATE Parts
               SET hours_confirmed_at=NULL
               WHERE hours_confirmed_at IS NOT NULL
                 AND (
                     part_no IN (SELECT part_no FROM ExternalGroups WHERE group_id IN (SELECT value FROM json_each(?)))
                     OR part_no IN (
                         SELECT part_no FROM PartOperations
                         WHERE status='active' AND ext_group_id IN (SELECT value FROM json_each(?))
                     )
                 )""",
            (groups_json, groups_json),
        )
        self.execute(
            """UPDATE PartOperations
               SET hours_confirmed_at=NULL
               WHERE status='active'
                 AND ext_group_id IN (SELECT value FROM json_each(?))
                 AND hours_confirmed_at IS NOT NULL""",
            (groups_json,),
        )

    def invalidate_op_type_confirmations(self, op_type_id: str) -> None:
        self.execute(
            "UPDATE Parts SET source_confirmed_at=NULL, hours_confirmed_at=NULL "
            "WHERE part_no IN (SELECT DISTINCT part_no FROM PartOperations WHERE op_type_id=? AND status='active') "
            "AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)",
            (op_type_id,),
        )
        self.execute(
            "UPDATE PartOperations SET source_confirmed_at=NULL, hours_confirmed_at=NULL "
            "WHERE op_type_id=? AND status='active' "
            "AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)",
            (op_type_id,),
        )

    def invalidate_supplier_confirmations(
        self, supplier_id: str, *, became_unavailable: bool, removed_op_types_json: Optional[str]
    ) -> None:
        if became_unavailable:
            where = _SUPPLIER_BASE_WHERE
            params: Tuple[Any, ...] = (supplier_id, supplier_id)
        elif removed_op_types_json is not None:
            where = _SUPPLIER_BASE_WHERE + " AND op_type_id IN (SELECT value FROM json_each(?))"
            params = (supplier_id, supplier_id, removed_op_types_json)
        else:
            return
        self.execute(
            "UPDATE Parts SET source_confirmed_at=NULL, hours_confirmed_at=NULL "
            "WHERE part_no IN (SELECT DISTINCT part_no FROM PartOperations WHERE " + where + ") "
            "AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)",
            params,
        )
        self.execute(
            "UPDATE PartOperations SET source_confirmed_at=NULL, hours_confirmed_at=NULL "
            "WHERE " + where + " AND (source_confirmed_at IS NOT NULL OR hours_confirmed_at IS NOT NULL)",
            params,
        )
