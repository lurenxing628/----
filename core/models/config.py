from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, get, parse_int


@dataclass
class ScheduleConfig:
    id: Optional[int]
    config_key: str
    config_value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleConfig:
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            config_key=str(get(row, "config_key") or ""),
            config_value=str(get(row, "config_value") or ""),
            description=get(row, "description"),
            updated_at=get(row, "updated_at"),
        )
