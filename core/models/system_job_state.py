from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, parse_optional_int


@dataclass
class SystemJobState:
    id: Optional[int]
    job_key: str
    last_run_time: Optional[str] = None
    last_run_detail: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> SystemJobState:
        return cls(
            id=parse_optional_int(row["id"], field="id"),
            job_key=str(row["job_key"]),
            last_run_time=row["last_run_time"],
            last_run_detail=row["last_run_detail"],
            updated_at=row["updated_at"],
        )
