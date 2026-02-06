from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class ExternalGroup:
    group_id: str
    part_no: str
    start_seq: int
    end_seq: int
    merge_mode: str = "separate"  # separate/merged
    total_days: Optional[float] = None
    supplier_id: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "ExternalGroup":
        start_seq = get(row, "start_seq")
        end_seq = get(row, "end_seq")
        total_days = get(row, "total_days")
        supplier_id = get(row, "supplier_id")
        return cls(
            group_id=str(get(row, "group_id") or ""),
            part_no=str(get(row, "part_no") or ""),
            start_seq=int(start_seq) if start_seq is not None and start_seq != "" else 0,
            end_seq=int(end_seq) if end_seq is not None and end_seq != "" else 0,
            merge_mode=(str(get(row, "merge_mode") or "separate").strip().lower() or "separate"),
            total_days=float(total_days) if total_days is not None and total_days != "" else None,
            supplier_id=str(supplier_id) if supplier_id is not None and supplier_id != "" else None,
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "group_id": self.group_id,
                "part_no": self.part_no,
                "start_seq": self.start_seq,
                "end_seq": self.end_seq,
                "merge_mode": self.merge_mode,
                "total_days": self.total_days,
                "supplier_id": self.supplier_id,
                "remark": self.remark,
                "created_at": self.created_at,
            }
        )

