from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from .enums import BatchPriority, BatchStatus, ReadyStatus


@dataclass
class Batch:
    batch_id: str
    part_no: str
    part_name: Optional[str] = None
    quantity: int = 0
    due_date: Optional[str] = None  # YYYY-MM-DD（SQLite DATE）
    priority: str = BatchPriority.NORMAL.value  # normal/urgent/critical
    ready_status: str = ReadyStatus.YES.value  # yes/no/partial
    ready_date: Optional[str] = None  # YYYY-MM-DD（SQLite DATE）；仅启用齐套检查时表示最早可开工日
    status: str = BatchStatus.PENDING.value  # pending/scheduled/processing/completed/cancelled
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "part_no": self.part_no,
            "part_name": self.part_name,
            "quantity": self.quantity,
            "due_date": self.due_date,
            "priority": self.priority,
            "ready_status": self.ready_status,
            "ready_date": self.ready_date,
            "status": self.status,
            "remark": self.remark,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
