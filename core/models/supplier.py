from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float


@dataclass
class Supplier:
    supplier_id: str
    name: str
    op_type_id: Optional[str] = None
    default_days: float = 1.0
    status: str = "active"  # active/inactive
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "Supplier":
        op_type_id = get(row, "op_type_id")
        default_days = parse_float(get(row, "default_days"), default=1.0)
        return cls(
            supplier_id=str(get(row, "supplier_id") or ""),
            name=str(get(row, "name") or ""),
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            default_days=default_days if default_days is not None else 1.0,
            status=(str(get(row, "status") or "active").strip().lower() or "active"),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "supplier_id": self.supplier_id,
                "name": self.name,
                "op_type_id": self.op_type_id,
                "default_days": self.default_days,
                "status": self.status,
                "remark": self.remark,
                "created_at": self.created_at,
            }
        )

