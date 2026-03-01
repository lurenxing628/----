from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float
from .enums import MaterialStatus


@dataclass
class Material:
    material_id: str
    name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    stock_qty: float = 0.0
    status: str = MaterialStatus.ACTIVE.value  # active/inactive
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> Material:
        return cls(
            material_id=str(get(row, "material_id") or ""),
            name=str(get(row, "name") or ""),
            spec=get(row, "spec"),
            unit=get(row, "unit"),
            stock_qty=parse_float(get(row, "stock_qty"), default=0.0) or 0.0,
            status=(
                str(get(row, "status") or MaterialStatus.ACTIVE.value).strip().lower()
                or MaterialStatus.ACTIVE.value
            ),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "material_id": self.material_id,
                "name": self.name,
                "spec": self.spec,
                "unit": self.unit,
                "stock_qty": self.stock_qty,
                "status": self.status,
                "remark": self.remark,
                "created_at": self.created_at,
            }
        )

