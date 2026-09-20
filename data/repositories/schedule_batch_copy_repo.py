"""Raw source-operation identities for batch copy; stored values are never coerced through a model."""

from __future__ import annotations

from typing import Any, List

from .base_repo import BaseRepository


class ScheduleBatchCopyRepository(BaseRepository):
    def source_operation_ids(self, batch_id: str) -> List[Any]:
        # 只读原始 ID，避免 model 把未知值、NULL 或 BLOB 转成默认值。
        rows = self.fetchall("SELECT id FROM BatchOperations WHERE batch_id = ? ORDER BY seq, piece_id", (batch_id,))
        return [row["id"] for row in rows]
