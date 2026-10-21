from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, get, parse_float_or_default, parse_int
from .enums import YesNo


@dataclass
class BatchMaterial:
    id: Optional[int]
    batch_id: str
    material_id: str
    required_qty: float
    available_qty: float = 0.0
    ready_status: str = YesNo.NO.value  # yes/no

    @classmethod
    def from_row(cls, row: RowLike) -> BatchMaterial:
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            batch_id=str(get(row, "batch_id") or ""),
            material_id=str(get(row, "material_id") or ""),
            required_qty=parse_float_or_default(get(row, "required_qty"), 0.0, field="required_qty"),
            available_qty=parse_float_or_default(get(row, "available_qty"), 0.0, field="available_qty"),
            ready_status=(str(get(row, "ready_status") or YesNo.NO.value).strip().lower() or YesNo.NO.value),
        )
