from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from core.models import Batch

from .base_repo import BaseRepository


class BatchRepository(BaseRepository):
    """批次仓库（Batches）。"""

    def get(self, batch_id: str) -> Optional[Batch]:
        row = self.fetchone(
            "SELECT batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark, created_at, updated_at FROM Batches WHERE batch_id = ?",
            (batch_id,),
        )
        return Batch.from_row(row) if row else None

    def list(
        self,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        part_no: Optional[str] = None,
    ) -> List[Batch]:
        sql = "SELECT batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark, created_at, updated_at FROM Batches"
        params: List[Any] = []
        where = []
        if status:
            where.append("status = ?")
            params.append(status)
        if priority:
            where.append("priority = ?")
            params.append(priority)
        if part_no:
            where.append("part_no = ?")
            params.append(part_no)
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY created_at DESC, batch_id"
        rows = self.fetchall(sql, tuple(params))
        return [Batch.from_row(r) for r in rows]

    def list_pending(self) -> List[Batch]:
        return self.list(status="pending")

    def create(self, batch: Union[Batch, Dict[str, Any]]) -> Batch:
        b = batch if isinstance(batch, Batch) else Batch.from_row(batch)
        self.execute(
            """
            INSERT INTO Batches
            (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                b.batch_id,
                b.part_no,
                b.part_name,
                int(b.quantity),
                b.due_date,
                b.priority,
                b.ready_status,
                b.ready_date,
                b.status,
                b.remark,
            ),
        )
        return b

    def update(self, batch_id: str, updates: Dict[str, Any]) -> None:
        self.execute(
            """
            UPDATE Batches
            SET
              part_no = COALESCE(?, part_no),
              part_name = COALESCE(?, part_name),
              quantity = COALESCE(?, quantity),
              due_date = COALESCE(?, due_date),
              priority = COALESCE(?, priority),
              ready_status = COALESCE(?, ready_status),
              ready_date = COALESCE(?, ready_date),
              status = COALESCE(?, status),
              remark = COALESCE(?, remark),
              updated_at = CURRENT_TIMESTAMP
            WHERE batch_id = ?
            """,
            (
                updates.get("part_no"),
                updates.get("part_name"),
                updates.get("quantity"),
                updates.get("due_date"),
                updates.get("priority"),
                updates.get("ready_status"),
                updates.get("ready_date"),
                updates.get("status"),
                updates.get("remark"),
                batch_id,
            ),
        )

    def delete(self, batch_id: str) -> None:
        self.execute("DELETE FROM Batches WHERE batch_id = ?", (batch_id,))

