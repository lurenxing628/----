from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class Part:
    part_no: str
    part_name: str
    route_raw: Optional[str] = None
    route_parsed: str = "no"  # yes/no
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "Part":
        return cls(
            part_no=str(get(row, "part_no") or ""),
            part_name=str(get(row, "part_name") or ""),
            route_raw=get(row, "route_raw"),
            route_parsed=(str(get(row, "route_parsed") or "no").strip().lower() or "no"),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "part_no": self.part_no,
                "part_name": self.part_name,
                "route_raw": self.route_raw,
                "route_parsed": self.route_parsed,
                "remark": self.remark,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

