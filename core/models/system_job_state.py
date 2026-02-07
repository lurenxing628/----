from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int


@dataclass
class SystemJobState:
    id: Optional[int]
    job_key: str
    last_run_time: Optional[str] = None
    last_run_detail: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "SystemJobState":
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            job_key=str(get(row, "job_key") or ""),
            last_run_time=get(row, "last_run_time"),
            last_run_detail=get(row, "last_run_detail"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "job_key": self.job_key,
                "last_run_time": self.last_run_time,
                "last_run_detail": self.last_run_detail,
                "updated_at": self.updated_at,
            }
        )

