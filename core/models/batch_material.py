from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float, parse_int


@dataclass
class BatchMaterial:
    id: Optional[int]
    batch_id: str
    material_id: str
    required_qty: float
    available_qty: float = 0.0
    ready_status: str = "no"  # yes/no

    @classmethod
    def from_row(cls, row: RowLike) -> "BatchMaterial":
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            batch_id=str(get(row, "batch_id") or ""),
            material_id=str(get(row, "material_id") or ""),
            required_qty=parse_float(get(row, "required_qty"), default=0.0) or 0.0,
            available_qty=parse_float(get(row, "available_qty"), default=0.0) or 0.0,
            ready_status=(str(get(row, "ready_status") or "no").strip().lower() or "no"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "batch_id": self.batch_id,
                "material_id": self.material_id,
                "required_qty": self.required_qty,
                "available_qty": self.available_qty,
                "ready_status": self.ready_status,
            }
        )

