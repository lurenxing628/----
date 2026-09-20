"""工艺工作流确认表（WorkbenchProcessWorkflow / WorkbenchProcessOperationConfirmations）的读写入口。

只做 SQL 执行与参数绑定；读方法按游标列名映射成 dict（不依赖连接的 row_factory），
阶段列名由本仓储内的白名单展开，裁决、签名与事务归调用方服务。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from .base_repo import BaseRepository

WORKFLOW_STAGES = ("route", "source", "hours")


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

    def active_operations(self, part_no: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._dict_rows("""SELECT o.*, r.ref, t.name AS type_name, t.category,
        tr.ref AS type_ref, p.default_merge_mode FROM PartOperations o
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_operation' AND r.active=1
            AND r.entity_key=CAST(o.id AS TEXT)
        LEFT JOIN OpTypes t ON t.op_type_id=o.op_type_id
        LEFT JOIN WorkbenchEntityRefs tr ON tr.kind='op_type' AND tr.active=1 AND tr.entity_key=t.op_type_id
        LEFT JOIN WorkbenchOpTypePolicies p ON p.op_type_id=t.op_type_id
        WHERE o.status='active'""" + (" AND o.part_no=?" if part_no is not None else "")
                               + " ORDER BY o.part_no, o.seq, o.id", (part_no,) if part_no is not None else ())

    def active_external_groups(self, part_no: Optional[str] = None) -> List[Dict[str, Any]]:
        return self._dict_rows("""SELECT g.*, r.ref FROM ExternalGroups g
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='template_external_group' AND r.active=1 AND r.entity_key=g.group_id
        WHERE g.group_id IN (SELECT ext_group_id FROM PartOperations WHERE status='active'"""
                               + (" AND part_no=?" if part_no is not None else "") + ")",
                               (part_no,) if part_no is not None else ())

    def supplier_facts(self) -> List[Dict[str, Any]]:
        return self._dict_rows("""
        SELECT s.supplier_id, s.op_type_id, s.status, r.ref, p.inactive_reason FROM Suppliers s
        LEFT JOIN WorkbenchEntityRefs r ON r.kind='supplier' AND r.active=1 AND r.entity_key=s.supplier_id
        LEFT JOIN WorkbenchSupplierProfiles p ON p.supplier_id=s.supplier_id""")

    def supplier_op_types(self) -> List[Dict[str, Any]]:
        return self._dict_rows("SELECT supplier_id, op_type_id FROM WorkbenchSupplierOpTypes")

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
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> None:
        self.execute(
            """INSERT INTO WorkbenchProcessOperationConfirmations
                (part_ref,operation_ref,stage,signature,confirmed_at,confirmed_by) VALUES (?,?,?,?,?,?)""",
            (part_ref, operation_ref, stage, signature, confirmed_at, confirmed_by),
        )

    def update_confirmation(
        self,
        *,
        part_ref: str,
        operation_ref: str,
        stage: str,
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> int:
        cursor = self.execute(
            """UPDATE WorkbenchProcessOperationConfirmations SET signature=?,confirmed_at=?,confirmed_by=?
                WHERE part_ref=? AND operation_ref=? AND stage=?""",
            (signature, confirmed_at, confirmed_by, part_ref, operation_ref, stage),
        )
        return int(cursor.rowcount)

    def delete_confirmations_outside_active_route(self, part_ref: str, part_no: str) -> int:
        cursor = self.execute(
            """DELETE FROM WorkbenchProcessOperationConfirmations WHERE part_ref=? AND operation_ref NOT IN (
                SELECT r.ref FROM PartOperations o JOIN WorkbenchEntityRefs r ON r.entity_key=CAST(o.id AS TEXT)
                WHERE r.kind='template_operation' AND r.active=1 AND o.part_no=? AND o.status='active')""",
            (part_ref, part_no),
        )
        return int(cursor.rowcount)

    def set_stage_confirmation(
        self,
        *,
        part_ref: str,
        stage: str,
        signature: str,
        confirmed_at: str,
        confirmed_by: Optional[str],
    ) -> int:
        if stage not in WORKFLOW_STAGES:
            raise ValueError(f"unknown workflow stage: {stage!r}")
        cursor = self.execute(
            f"""UPDATE WorkbenchProcessWorkflow SET {stage}_signature=?,
                {stage}_confirmed_at=?,{stage}_confirmed_by=? WHERE part_ref=?""",
            (signature, confirmed_at, confirmed_by, part_ref),
        )
        return int(cursor.rowcount)
