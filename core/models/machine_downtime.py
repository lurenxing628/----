from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class MachineDowntime:
    """
    设备停机时间段（MachineDowntimes）。

    说明：
    - 用于表达“设备资源在某时间段不可用”（计划停机/故障/停电等）
    - 与 Machines.status（长期状态）并存
    """

    id: Optional[int] = None
    machine_id: str = ""
    start_time: str = ""
    end_time: str = ""
    reason_code: Optional[str] = None
    reason_detail: Optional[str] = None
    status: str = "active"  # active/cancelled
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "MachineDowntime":
        raw_id = get(row, "id")
        try:
            _id = int(raw_id) if raw_id is not None and str(raw_id).strip() != "" else None
        except Exception:
            _id = None
        return cls(
            id=_id,
            machine_id=str(get(row, "machine_id") or ""),
            start_time=str(get(row, "start_time") or ""),
            end_time=str(get(row, "end_time") or ""),
            reason_code=get(row, "reason_code"),
            reason_detail=get(row, "reason_detail"),
            status=str(get(row, "status") or "active"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "machine_id": self.machine_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "reason_code": self.reason_code,
                "reason_detail": self.reason_detail,
                "status": self.status,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )

