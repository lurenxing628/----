from __future__ import annotations

from typing import Any, Dict, Optional

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

    def create(self, batch: Batch) -> None:
        self.execute(
            """
            INSERT INTO Batches
            (batch_id, part_no, part_name, quantity, due_date, priority, ready_status, ready_date, status, remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                batch.batch_id,
                batch.part_no,
                batch.part_name,
                batch.quantity,
                batch.due_date,
                batch.priority,
                batch.ready_status,
                batch.ready_date,
                batch.status,
                batch.remark,
            ),
        )

    def update(self, batch_id: str, updates: Dict[str, Any]) -> None:
        """
        动态更新：只更新 updates 中出现的字段；
        - 允许显式传入 None 将可空列置 NULL
        - 避免 COALESCE 造成“无法置空”
        """
        set_parts = [f"{k} = ?" for k in updates] + ["updated_at = CURRENT_TIMESTAMP"]
        params = [*updates.values(), batch_id]
        sql = f"UPDATE Batches SET {', '.join(set_parts)} WHERE batch_id = ?"
        self.execute(sql, tuple(params))

    def delete(self, batch_id: str) -> None:
        self.execute("DELETE FROM Batches WHERE batch_id = ?", (batch_id,))
