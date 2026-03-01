from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_float, parse_int
from .enums import MergeMode


@dataclass
class ExternalGroup:
    group_id: str
    part_no: str
    start_seq: int
    end_seq: int
    merge_mode: str = MergeMode.SEPARATE.value  # separate/merged
    total_days: Optional[float] = None
    supplier_id: Optional[str] = None
    remark: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ExternalGroup:
        raw_start_seq = get(row, "start_seq")
        raw_end_seq = get(row, "end_seq")
        start_seq = parse_int(raw_start_seq, default=0) or 0
        end_seq = parse_int(raw_end_seq, default=0) or 0
        # 防御：序号范围应满足 start_seq <= end_seq
        if start_seq > end_seq:
            start_seq, end_seq = end_seq, start_seq

        total_days = parse_float(get(row, "total_days"), default=None)
        supplier_id = get(row, "supplier_id")
        return cls(
            group_id=str(get(row, "group_id") or ""),
            part_no=str(get(row, "part_no") or ""),
            start_seq=start_seq,
            end_seq=end_seq,
            merge_mode=(
                str(get(row, "merge_mode") or MergeMode.SEPARATE.value).strip().lower() or MergeMode.SEPARATE.value
            ),
            total_days=total_days,
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

