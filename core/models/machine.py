from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ._helpers import RowLike
from .enums import MachineStatus


@dataclass
class Machine:
    machine_id: str
    name: str
    #: 设备能做的全部工种；唯一存储是 MachineOpTypes，可以为空。
    op_type_ids: Tuple[str, ...]
    category: Optional[str] = None
    status: str = MachineStatus.ACTIVE.value  # active/inactive/maintain
    remark: Optional[str] = None
    team_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> Machine:
        category = row["category"]
        team_id = row["team_id"]
        return cls(
            machine_id=str(row["machine_id"] or ""),
            name=str(row["name"]),
            op_type_ids=tuple(row["op_type_ids"]),
            category=str(category) if category is not None and category != "" else None,
            status=row["status"],
            remark=row["remark"],
            team_id=str(team_id) if team_id is not None and team_id != "" else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
