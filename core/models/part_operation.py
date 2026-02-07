from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float, parse_int


@dataclass
class PartOperation:
    id: Optional[int]
    part_no: str
    seq: int
    op_type_id: Optional[str] = None
    op_type_name: str = ""
    source: str = "internal"  # internal/external
    supplier_id: Optional[str] = None
    ext_days: Optional[float] = None
    ext_group_id: Optional[str] = None
    setup_hours: float = 0.0
    unit_hours: float = 0.0
    status: str = "active"  # active/deleted
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "PartOperation":
        raw_id = get(row, "id")
        raw_seq = get(row, "seq")
        setup_hours = get(row, "setup_hours")
        unit_hours = get(row, "unit_hours")
        ext_days = get(row, "ext_days")
        op_type_id = get(row, "op_type_id")
        supplier_id = get(row, "supplier_id")
        ext_group_id = get(row, "ext_group_id")
        return cls(
            id=parse_int(raw_id, default=None),
            part_no=str(get(row, "part_no") or ""),
            seq=parse_int(raw_seq, default=0) or 0,
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            op_type_name=str(get(row, "op_type_name") or ""),
            source=(str(get(row, "source") or "internal").strip().lower() or "internal"),
            supplier_id=str(supplier_id) if supplier_id is not None and supplier_id != "" else None,
            ext_days=parse_float(ext_days, default=None),
            ext_group_id=str(ext_group_id) if ext_group_id is not None and ext_group_id != "" else None,
            setup_hours=parse_float(setup_hours, default=0.0) or 0.0,
            unit_hours=parse_float(unit_hours, default=0.0) or 0.0,
            status=(str(get(row, "status") or "active").strip().lower() or "active"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "part_no": self.part_no,
                "seq": self.seq,
                "op_type_id": self.op_type_id,
                "op_type_name": self.op_type_name,
                "source": self.source,
                "supplier_id": self.supplier_id,
                "ext_days": self.ext_days,
                "ext_group_id": self.ext_group_id,
                "setup_hours": self.setup_hours,
                "unit_hours": self.unit_hours,
                "status": self.status,
                "created_at": self.created_at,
            }
        )

