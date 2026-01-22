from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import BatchOperation

from .base_repo import BaseRepository


class BatchOperationRepository(BaseRepository):
    """批次工序仓库（BatchOperations）。"""

    def get(self, op_id: int) -> Optional[BatchOperation]:
        row = self.fetchone(
            """
            SELECT id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                   machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status, created_at
            FROM BatchOperations
            WHERE id = ?
            """,
            (int(op_id),),
        )
        return BatchOperation.from_row(row) if row else None

    def get_by_op_code(self, op_code: str) -> Optional[BatchOperation]:
        row = self.fetchone(
            """
            SELECT id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                   machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status, created_at
            FROM BatchOperations
            WHERE op_code = ?
            """,
            (op_code,),
        )
        return BatchOperation.from_row(row) if row else None

    def list_by_batch(self, batch_id: str) -> List[BatchOperation]:
        rows = self.fetchall(
            """
            SELECT id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                   machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status, created_at
            FROM BatchOperations
            WHERE batch_id = ?
            ORDER BY seq, piece_id
            """,
            (batch_id,),
        )
        return [BatchOperation.from_row(r) for r in rows]

    def list_by_status(self, status: str) -> List[BatchOperation]:
        rows = self.fetchall(
            """
            SELECT id, op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
                   machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status, created_at
            FROM BatchOperations
            WHERE status = ?
            ORDER BY created_at DESC, batch_id, seq
            """,
            (status,),
        )
        return [BatchOperation.from_row(r) for r in rows]

    def create(self, op: Union[BatchOperation, Dict[str, Any]]) -> BatchOperation:
        bo = op if isinstance(op, BatchOperation) else BatchOperation.from_row(op)
        cur = self.execute(
            """
            INSERT INTO BatchOperations
            (op_code, batch_id, piece_id, seq, op_type_id, op_type_name, source,
             machine_id, operator_id, supplier_id, setup_hours, unit_hours, ext_days, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                bo.op_code,
                bo.batch_id,
                bo.piece_id,
                int(bo.seq),
                bo.op_type_id,
                bo.op_type_name,
                bo.source,
                bo.machine_id,
                bo.operator_id,
                bo.supplier_id,
                bo.setup_hours,
                bo.unit_hours,
                bo.ext_days,
                bo.status,
            ),
        )
        bo.id = int(cur.lastrowid) if cur.lastrowid is not None else bo.id
        return bo

    def update(self, op_id: int, updates: Dict[str, Any]) -> None:
        """
        更新批次工序（允许显式清空字段为 NULL）。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 machine_id/operator_id/supplier_id/ext_days 等显式清空为 NULL
          （否则 COALESCE 会导致无法“取消选择/清空”）
        """
        if not updates:
            return

        allowed = {
            "piece_id",
            "seq",
            "op_type_id",
            "op_type_name",
            "source",
            "machine_id",
            "operator_id",
            "supplier_id",
            "setup_hours",
            "unit_hours",
            "ext_days",
            "status",
        }
        set_parts: List[str] = []
        params: List[Any] = []

        for key in (
            "piece_id",
            "seq",
            "op_type_id",
            "op_type_name",
            "source",
            "machine_id",
            "operator_id",
            "supplier_id",
            "setup_hours",
            "unit_hours",
            "ext_days",
            "status",
        ):
            if key not in allowed:
                continue
            if key in updates:
                set_parts.append(f"{key} = ?")
                params.append(updates.get(key))

        if not set_parts:
            return

        params.append(int(op_id))
        sql = f"UPDATE BatchOperations SET {', '.join(set_parts)} WHERE id = ?"
        self.execute(sql, tuple(params))

    def delete(self, op_id: int) -> None:
        self.execute("DELETE FROM BatchOperations WHERE id = ?", (int(op_id),))

    def delete_by_batch(self, batch_id: str) -> None:
        self.execute("DELETE FROM BatchOperations WHERE batch_id = ?", (batch_id,))

