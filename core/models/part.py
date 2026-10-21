from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, get
from .enums import YesNo


@dataclass
class Part:
    part_no: str
    part_name: str
    route_raw: Optional[str] = None
    route_parsed: str = YesNo.NO.value  # yes/no
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> Part:
        return cls(
            part_no=str(get(row, "part_no") or ""),
            part_name=str(get(row, "part_name") or ""),
            route_raw=get(row, "route_raw"),
            route_parsed=(str(get(row, "route_parsed") or YesNo.NO.value).strip().lower() or YesNo.NO.value),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )
