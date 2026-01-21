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
        self.execute(
            """
            UPDATE BatchOperations
            SET
              piece_id = COALESCE(?, piece_id),
              seq = COALESCE(?, seq),
              op_type_id = COALESCE(?, op_type_id),
              op_type_name = COALESCE(?, op_type_name),
              source = COALESCE(?, source),
              machine_id = COALESCE(?, machine_id),
              operator_id = COALESCE(?, operator_id),
              supplier_id = COALESCE(?, supplier_id),
              setup_hours = COALESCE(?, setup_hours),
              unit_hours = COALESCE(?, unit_hours),
              ext_days = COALESCE(?, ext_days),
              status = COALESCE(?, status)
            WHERE id = ?
            """,
            (
                updates.get("piece_id"),
                updates.get("seq"),
                updates.get("op_type_id"),
                updates.get("op_type_name"),
                updates.get("source"),
                updates.get("machine_id"),
                updates.get("operator_id"),
                updates.get("supplier_id"),
                updates.get("setup_hours"),
                updates.get("unit_hours"),
                updates.get("ext_days"),
                updates.get("status"),
                int(op_id),
            ),
        )

    def delete(self, op_id: int) -> None:
        self.execute("DELETE FROM BatchOperations WHERE id = ?", (int(op_id),))

    def delete_by_batch(self, batch_id: str) -> None:
        self.execute("DELETE FROM BatchOperations WHERE batch_id = ?", (batch_id,))

