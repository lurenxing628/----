from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int


@dataclass
class ScheduleHistory:
    id: Optional[int]
    schedule_time: Optional[str] = None
    version: int = 1
    strategy: str = ""
    batch_count: Optional[int] = None
    op_count: Optional[int] = None
    result_status: Optional[str] = None
    result_summary: Optional[str] = None  # JSON 字符串
    created_by: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "ScheduleHistory":
        raw_id = get(row, "id")
        version = get(row, "version")
        batch_count = get(row, "batch_count")
        op_count = get(row, "op_count")
        ver = parse_int(version, default=1)
        return cls(
            id=parse_int(raw_id, default=None),
            schedule_time=get(row, "schedule_time"),
            version=ver if ver is not None else 1,
            strategy=str(get(row, "strategy") or ""),
            batch_count=parse_int(batch_count, default=None),
            op_count=parse_int(op_count, default=None),
            result_status=get(row, "result_status"),
            result_summary=get(row, "result_summary"),
            created_by=get(row, "created_by"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "schedule_time": self.schedule_time,
                "version": self.version,
                "strategy": self.strategy,
                "batch_count": self.batch_count,
                "op_count": self.op_count,
                "result_status": self.result_status,
                "result_summary": self.result_summary,
                "created_by": self.created_by,
            }
        )

