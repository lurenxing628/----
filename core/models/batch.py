from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class Batch:
    batch_id: str
    part_no: str
    part_name: Optional[str] = None
    quantity: int = 0
    due_date: Optional[str] = None  # YYYY-MM-DD（SQLite DATE）
    priority: str = "normal"  # normal/urgent/critical
    ready_status: str = "yes"  # yes/no/partial
    ready_date: Optional[str] = None  # YYYY-MM-DD（SQLite DATE）；可选，表示最早可开工日
    status: str = "pending"  # pending/scheduled/processing/completed/cancelled
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "Batch":
        qty = get(row, "quantity")
        return cls(
            batch_id=str(get(row, "batch_id") or ""),
            part_no=str(get(row, "part_no") or ""),
            part_name=get(row, "part_name"),
            quantity=int(qty) if qty is not None and qty != "" else 0,
            due_date=get(row, "due_date"),
            priority=(str(get(row, "priority") or "normal").strip().lower() or "normal"),
            ready_status=(str(get(row, "ready_status") or "yes").strip().lower() or "yes"),
            ready_date=get(row, "ready_date"),
            status=(str(get(row, "status") or "pending").strip().lower() or "pending"),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
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
        )

