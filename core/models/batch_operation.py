from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float, parse_int
from .enums import BatchOperationStatus, SourceType


@dataclass
class BatchOperation:
    id: Optional[int]
    op_code: str
    batch_id: str
    piece_id: Optional[str] = None
    seq: int = 0
    op_type_id: Optional[str] = None
    op_type_name: str = ""
    source: str = SourceType.INTERNAL.value  # internal/external
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    supplier_id: Optional[str] = None
    setup_hours: float = 0.0
    unit_hours: float = 0.0
    ext_days: Optional[float] = None
    status: str = BatchOperationStatus.PENDING.value  # pending/scheduled/processing/completed/skipped
    created_at: Optional[str] = None

    def is_external(self) -> bool:
        return str(self.source or "").strip().lower() == SourceType.EXTERNAL.value

    def is_internal(self) -> bool:
        return str(self.source or "").strip().lower() == SourceType.INTERNAL.value

    def is_pending(self) -> bool:
        return str(self.status or "").strip().lower() == BatchOperationStatus.PENDING.value

    def is_scheduled(self) -> bool:
        return str(self.status or "").strip().lower() == BatchOperationStatus.SCHEDULED.value

    def is_processing(self) -> bool:
        return str(self.status or "").strip().lower() == BatchOperationStatus.PROCESSING.value

    def is_completed(self) -> bool:
        return str(self.status or "").strip().lower() == BatchOperationStatus.COMPLETED.value

    def is_skipped(self) -> bool:
        return str(self.status or "").strip().lower() == BatchOperationStatus.SKIPPED.value

    def has_supplier(self) -> bool:
        return bool(str(self.supplier_id or "").strip())

    def processing_hours(self) -> float:
        return float(self.setup_hours or 0.0) + float(self.unit_hours or 0.0)

    @classmethod
    def from_row(cls, row: RowLike) -> BatchOperation:
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
            id=parse_int(raw_id, default=None),
            op_code=str(get(row, "op_code") or ""),
            batch_id=str(get(row, "batch_id") or ""),
            piece_id=str(piece_id) if piece_id is not None and piece_id != "" else None,
            seq=parse_int(seq, default=0) or 0,
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            op_type_name=str(get(row, "op_type_name") or ""),
            source=(
                str(get(row, "source") or SourceType.INTERNAL.value).strip().lower() or SourceType.INTERNAL.value
            ),
            machine_id=str(machine_id) if machine_id is not None and machine_id != "" else None,
            operator_id=str(operator_id) if operator_id is not None and operator_id != "" else None,
            supplier_id=str(supplier_id) if supplier_id is not None and supplier_id != "" else None,
            setup_hours=parse_float(setup_hours, default=0.0) or 0.0,
            unit_hours=parse_float(unit_hours, default=0.0) or 0.0,
            ext_days=parse_float(ext_days, default=None),
            status=(
                str(get(row, "status") or BatchOperationStatus.PENDING.value).strip().lower()
                or BatchOperationStatus.PENDING.value
            ),
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
