from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, get, parse_optional_float
from .enums import OpTypeCategory


@dataclass
class OpType:
    op_type_id: str
    name: str
    category: str = OpTypeCategory.INTERNAL.value  # internal/external/both
    default_hours: Optional[float] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OpType:
        val = get(row, "default_hours")
        return cls(
            op_type_id=str(get(row, "op_type_id") or ""),
            name=str(get(row, "name") or ""),
            category=(str(get(row, "category") or OpTypeCategory.INTERNAL.value).strip().lower() or OpTypeCategory.INTERNAL.value),
            default_hours=parse_optional_float(val, field="default_hours"),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
        )
