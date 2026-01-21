from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class BatchOperation:
    id: Optional[int]
    op_code: str
    batch_id: str
    piece_id: Optional[str] = None
    seq: int = 0
    op_type_id: Optional[str] = None
    op_type_name: str = ""
    source: str = "internal"  # internal/external
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    supplier_id: Optional[str] = None
    setup_hours: float = 0.0
    unit_hours: float = 0.0
    ext_days: Optional[float] = None
    status: str = "pending"  # pending/scheduled/processing/completed/skipped
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "BatchOperation":
        raw_id = get(row, "id")
        seq = get(row, "seq")
        setup_hours = get(row, "setup_hours")
        unit_hours = get(row, "unit_hours")
        ext_days = get(row, "ext_days")
        op_type_id = get(row, "op_type_id")
        machine_id = get(row, "machine_id")
        operator_id = get(row, "operator_id")
        supplier_id = get(row, "supplier_id")
        piece_id = get(row, "piece_id")
        return cls(
            id=int(raw_id) if raw_id is not None and raw_id != "" else None,
            op_code=str(get(row, "op_code") or ""),
            batch_id=str(get(row, "batch_id") or ""),
            piece_id=str(piece_id) if piece_id is not None and piece_id != "" else None,
            seq=int(seq) if seq is not None and seq != "" else 0,
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            op_type_name=str(get(row, "op_type_name") or ""),
            source=str(get(row, "source") or "internal"),
            machine_id=str(machine_id) if machine_id is not None and machine_id != "" else None,
            operator_id=str(operator_id) if operator_id is not None and operator_id != "" else None,
            supplier_id=str(supplier_id) if supplier_id is not None and supplier_id != "" else None,
            setup_hours=float(setup_hours) if setup_hours is not None and setup_hours != "" else 0.0,
            unit_hours=float(unit_hours) if unit_hours is not None and unit_hours != "" else 0.0,
            ext_days=float(ext_days) if ext_days is not None and ext_days != "" else None,
            status=str(get(row, "status") or "pending"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "op_code": self.op_code,
                "batch_id": self.batch_id,
                "piece_id": self.piece_id,
                "seq": self.seq,
                "op_type_id": self.op_type_id,
                "op_type_name": self.op_type_name,
                "source": self.source,
                "machine_id": self.machine_id,
                "operator_id": self.operator_id,
                "supplier_id": self.supplier_id,
                "setup_hours": self.setup_hours,
                "unit_hours": self.unit_hours,
                "ext_days": self.ext_days,
                "status": self.status,
                "created_at": self.created_at,
            }
        )

