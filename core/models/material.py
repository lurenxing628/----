from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class Material:
    material_id: str
    name: str
    spec: Optional[str] = None
    unit: Optional[str] = None
    stock_qty: float = 0.0
    status: str = "active"  # active/inactive
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "Material":
        def _f(x, default: float = 0.0) -> float:
            try:
                return float(x)
            except Exception:
                return float(default)

        return cls(
            material_id=str(get(row, "material_id") or ""),
            name=str(get(row, "name") or ""),
            spec=get(row, "spec"),
            unit=get(row, "unit"),
            stock_qty=_f(get(row, "stock_qty"), 0.0),
            status=str(get(row, "status") or "active"),
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

