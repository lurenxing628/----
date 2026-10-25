"""工艺工作流确认表（WorkbenchProcessWorkflow / WorkbenchProcessOperationConfirmations）的读写入口。

只做 SQL 执行与参数绑定；读方法按游标列名映射成 dict（不依赖连接的 row_factory），
阶段列名由调用方服务受控传入，裁决、签名与事务归调用方服务。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .base_repo import BaseRepository
from .sqlite_rows import sql_order
from .workbench_execution_repo import chunks

_PART_SCOPE = """WITH related_groups AS (
    SELECT group_id FROM ExternalGroups WHERE part_no=?
    UNION
    SELECT ext_group_id FROM PartOperations
    WHERE status='active' AND part_no=? AND ext_group_id IS NOT NULL
) """


def operation_order(row: Mapping[str, Any]) -> Tuple[Tuple[int, Any], ...]:
    """在内存里合并工序行时复现 ORDER BY o.part_no, o.seq, o.id。"""
    return (sql_order(row["part_no"]), sql_order(row["seq"]), sql_order(row["id"]))


class WorkbenchProcessWorkflowRepository(BaseRepository):
    # -------------------------
    # 读：模板、工序、外协组、供应商与确认记录
    # -------------------------
    def _dict_rows(self, sql: str, params: Sequence[Any] = ()) -> List[Dict[str, Any]]:
        cursor = self.execute(sql, params)
        names = [column[0] for column in cursor.description]
        return [dict(zip(names, row)) for row in cursor]

    def part_with_ref(self, part_no: str) -> List[Dict[str, Any]]:
        return self._dict_rows("""SELECT p.*, r.ref FROM Parts p LEFT JOIN WorkbenchEntityRefs r
        ON r.kind='part' AND r.active=1 AND r.entity_key=p.part_no WHERE p.part_no=?""", (part_no,))

    def parts_with_refs(self) -> List[Dict[str, Any]]:
        return self._dict_rows("""SELECT p.*, r.ref FROM Parts p LEFT JOIN WorkbenchEntityRefs r
            ON r.kind='part' AND r.active=1 AND r.entity_key=p.part_no ORDER BY p.part_no""")

    def stored_workflow(self, part_ref: str) -> List[Dict[str, Any]]:
        return self._dict_rows("SELECT * FROM WorkbenchProcessWorkflow WHERE part_ref=?", (part_ref,))

    def stored_workflows(self) -> List[Dict[str, Any]]:
        return self._dict_rows("SELECT * FROM WorkbenchProcessWorkflow")

    def active_operations(
        self, part_no: Optional[str] = None, *, include_related_groups: bool = True
    ) -> List[Dict[str, Any]]:
        sql = """SELECT o.*, r.ref, t.name AS type_name, t.category,
        tr.ref AS type_ref, p.default_merge_mode FROM PartOperations o
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
            AND r.entity_key=CAST(o.id AS TEXT)
        LEFT JOIN OpTypes t ON t.op_type_id=o.op_type_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='op_type' AND tr.active=1 AND tr.entity_key=t.op_type_id
        LEFT JOIN WorkbenchOpTypePolicies p ON p.op_type_id=t.op_type_id
        WHERE o.status='active'"""
        if part_no is None:
            return self._dict_rows(sql + " ORDER BY o.part_no, o.seq, o.id")
        part_rows = self._dict_rows(sql + " AND o.part_no=? ORDER BY o.part_no, o.seq, o.id", (part_no,))
        if not include_related_groups:
            return part_rows
        group_ids = {row["ext_group_id"] for row in part_rows if row["ext_group_id"] is not None}
        group_ids.update(
            row[0] for row in self.execute("SELECT group_id FROM ExternalGroups WHERE part_no=?", (part_no,))
        )
        if not group_ids:
            return part_rows
        related_rows: List[Dict[str, Any]] = []
        for chunk in chunks(list(group_ids)):
            marks = ",".join("?" for _ in chunk)
            related_rows.extend(
                self._dict_rows(
                    sql + f" AND o.part_no<>? AND o.ext_group_id IN ({marks})",
                    (part_no, *chunk),
                )
            )
        if not related_rows:
            return part_rows
        combined = part_rows + related_rows
        combined.sort(key=operation_order)
        return combined

    def active_external_groups(self, part_no: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = """SELECT g.*, r.ref FROM ExternalGroups g
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.active=1 AND r.entity_key=g.group_id """
        if part_no is None:
            return self._dict_rows(sql + "WHERE g.group_id IN (SELECT ext_group_id FROM PartOperations WHERE status='active')")
        return self._dict_rows(_PART_SCOPE + sql + "WHERE g.group_id IN (SELECT group_id FROM related_groups)",
                               (part_no, part_no))

    def _supplier_rows(self, sql, supplier_ids):
        if supplier_ids is None:
            return self._dict_rows(sql)
        result = []
        for chunk in chunks(supplier_ids):
            marks = ",".join("?" for _ in chunk)
            result.extend(self._dict_rows(sql + " WHERE s.supplier_id IN (" + marks + ")", chunk))
        return result

    def supplier_facts(self, supplier_ids: Optional[Sequence[Any]]) -> List[Dict[str, Any]]:
        return self._supplier_rows("""
        SELECT s.supplier_id, s.op_type_id, s.status, r.ref, p.inactive_reason FROM Suppliers s
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='supplier' AND r.active=1 AND r.entity_key=s.supplier_id
        LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id""", supplier_ids)

    def supplier_op_types(self, supplier_ids: Optional[Sequence[Any]]) -> List[Dict[str, Any]]:
        return self._supplier_rows("SELECT supplier_id, op_type_id FROM WorkbenchSupplierOpTypes s", supplier_ids)

    def confirmations(self, part_no: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._dict_rows("SELECT c.* FROM WorkbenchProcessOperationConfirmations c" + (
            " JOIN WorkbenchEntityRefs r ON r.ref=c.part_ref WHERE r.kind='part' AND r.active=1 AND r.entity_key=?"
            if part_no is not None else ""), (part_no,) if part_no is not None else ())

    # -------------------------
    # 写：工作流登记与确认记录
    # -------------------------
    def insert_workflow(self, part_ref: str) -> None:
        self.execute("INSERT INTO WorkbenchProcessWorkflow(part_ref) VALUES (?)", (part_ref,))

    def insert_confirmation(
        self,
        *,
        part_ref: str,
        operation_ref: str,
        stage: str,
        content_json: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> None:
        self.execute(
            """INSERT INTO WorkbenchProcessOperationConfirmations
                (part_ref,operation_ref,stage,signature,confirmed_at,confirmed_by,content_json)
                VALUES (?,?,?,NULL,?,?,?)""",
            (part_ref, operation_ref, stage, confirmed_at, confirmed_by, content_json),
        )

    def update_confirmation(
        self,
        *,
        part_ref: str,
        operation_ref: str,
        stage: str,
        content_json: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> None:
        self.execute(
            """UPDATE WorkbenchProcessOperationConfirmations SET content_json=?,confirmed_at=?,confirmed_by=?
                WHERE part_ref=? AND operation_ref=? AND stage=?""",
            (content_json, confirmed_at, confirmed_by, part_ref, operation_ref, stage),
        )

    def delete_confirmations_outside_active_route(self, part_ref: str, part_no: str) -> None:
        self.execute(
            """DELETE FROM WorkbenchProcessOperationConfirmations WHERE part_ref=? AND operation_ref NOT IN (
                SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.part_no=? AND o.status='active')""",
            (part_ref, part_no),
        )

    def set_stage_confirmation(
        self,
        *,
        part_ref: str,
        stage: str,
        content_json: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> None:
        self.execute(
            f"""UPDATE WorkbenchProcessWorkflow SET {stage}_content_json=?,
                {stage}_confirmed_at=?,{stage}_confirmed_by=? WHERE part_ref=?""",
            (content_json, confirmed_at, confirmed_by, part_ref),
        )
