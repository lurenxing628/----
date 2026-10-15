"""Raw source-operation identities for batch copy; stored values are never coerced through a model."""

from __future__ import annotations

from typing import Any, List

from .base_repo import BaseRepository
from .workbench_template_lineage_repo import INSTANCE_FROM, INSTANCE_SELECT


class ScheduleBatchCopyRepository(BaseRepository):
    def source_instances(self, batch_id: str) -> List[Any]:
        return self.fetchall(INSTANCE_SELECT + INSTANCE_FROM + " WHERE o.batch_id=? ORDER BY o.seq, o.piece_id", (batch_id,))
