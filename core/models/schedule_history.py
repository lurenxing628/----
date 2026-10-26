from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, parse_int, parse_optional_int


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
        return cls(
            id=parse_optional_int(row["id"], field="id"),
            schedule_time=row["schedule_time"],
            version=parse_int(row["version"], field="version"),
            strategy=str(row["strategy"]),
            batch_count=parse_optional_int(row["batch_count"], field="batch_count"),
            op_count=parse_optional_int(row["op_count"], field="op_count"),
            result_status=row["result_status"],
            result_summary=row["result_summary"],
            created_by=row["created_by"],
        )
