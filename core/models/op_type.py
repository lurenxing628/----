from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float


@dataclass
class OpType:
    op_type_id: str
    name: str
    category: str = "internal"  # internal/external
    default_hours: Optional[float] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "OpType":
        val = get(row, "default_hours")
        return cls(
            op_type_id=str(get(row, "op_type_id") or ""),
            name=str(get(row, "name") or ""),
            category=(str(get(row, "category") or "internal").strip().lower() or "internal"),
            default_hours=parse_float(val, default=None),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "op_type_id": self.op_type_id,
                "name": self.name,
                "category": self.category,
                "default_hours": self.default_hours,
                "remark": self.remark,
                "created_at": self.created_at,
            }
        )

