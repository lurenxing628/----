from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int
from .enums import LockStatus


@dataclass
class Schedule:
    id: Optional[int]
    op_id: Optional[int] = None
    machine_id: Optional[str] = None
    operator_id: Optional[str] = None
    start_time: str = ""
    end_time: str = ""
    lock_status: str = LockStatus.UNLOCKED.value  # V1 仅占位（不做资源锁）
    version: int = 1
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> Schedule:
        raw_id = get(row, "id")
        op_id = get(row, "op_id")
        version = get(row, "version")
        machine_id = get(row, "machine_id")
        operator_id = get(row, "operator_id")
        return cls(
            id=parse_int(raw_id, default=None),
            op_id=parse_int(op_id, default=None),
            machine_id=str(machine_id) if machine_id is not None and machine_id != "" else None,
            operator_id=str(operator_id) if operator_id is not None and operator_id != "" else None,
            start_time=str(get(row, "start_time") or ""),
            end_time=str(get(row, "end_time") or ""),
            lock_status=(
                str(get(row, "lock_status") or LockStatus.UNLOCKED.value).strip().lower() or LockStatus.UNLOCKED.value
            ),
            version=parse_int(version, default=1),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "op_id": self.op_id,
                "machine_id": self.machine_id,
                "operator_id": self.operator_id,
                "start_time": self.start_time,
                "end_time": self.end_time,
                "lock_status": self.lock_status,
                "version": self.version,
                "created_at": self.created_at,
            }
        )

