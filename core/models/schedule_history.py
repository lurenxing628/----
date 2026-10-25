from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, parse_int


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
    def from_row(cls, row: RowLike) -> ScheduleHistory:
        ver = parse_int(row["version"], default=1)
        return cls(
            id=parse_int(row["id"], default=None),
            schedule_time=row["schedule_time"],
            version=ver if ver is not None else 1,
            strategy=str(row["strategy"] or ""),
            batch_count=parse_int(row["batch_count"], default=None),
            op_count=parse_int(row["op_count"], default=None),
            result_status=row["result_status"],
            result_summary=row["result_summary"],
            created_by=row["created_by"],
        )
