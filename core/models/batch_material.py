from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


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
        def _f(x, default: float = 0.0) -> float:
            try:
                return float(x)
            except Exception:
                return float(default)

        raw_id = get(row, "id")
        return cls(
            id=int(raw_id) if raw_id is not None and raw_id != "" else None,
            batch_id=str(get(row, "batch_id") or ""),
            material_id=str(get(row, "material_id") or ""),
            required_qty=_f(get(row, "required_qty"), 0.0),
            available_qty=_f(get(row, "available_qty"), 0.0),
            ready_status=str(get(row, "ready_status") or "no"),
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

