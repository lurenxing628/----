from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class Machine:
    machine_id: str
    name: str
    op_type_id: Optional[str] = None
    category: Optional[str] = None
    status: str = "active"  # active/inactive/maintain
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "Machine":
        op_type_id = get(row, "op_type_id")
        category = get(row, "category")
        return cls(
            machine_id=str(get(row, "machine_id") or ""),
            name=str(get(row, "name") or ""),
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            category=str(category) if category is not None and category != "" else None,
            status=str(get(row, "status") or "active"),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "machine_id": self.machine_id,
                "name": self.name,
                "op_type_id": self.op_type_id,
                "category": self.category,
                "status": self.status,
                "remark": self.remark,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

