from __future__ import annotations

from typing import Any, Dict

from .base_repo import BaseRepository


class BatchOperationRepository(BaseRepository):
    """批次工序仓库（BatchOperations）。"""

    def update(self, op_id: int, updates: Dict[str, Any]) -> None:
        """
        更新批次工序（允许显式清空字段为 NULL）。

        说明：
        - 只更新 updates 中出现的字段
        - 允许把 machine_id/operator_id/supplier_id/ext_days 等显式清空为 NULL
          （否则 COALESCE 会导致无法“取消选择/清空”）
        """
        set_parts = [f"{k} = ?" for k in updates]
        params = [*updates.values(), op_id]
        sql = f"UPDATE BatchOperations SET {', '.join(set_parts)} WHERE id = ?"
        self.execute(sql, tuple(params))

    def delete_by_batch(self, batch_id: str) -> None:
        self.execute("DELETE FROM BatchOperations WHERE batch_id = ?", (batch_id,))
