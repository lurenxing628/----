from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from ._helpers import RowLike
from .enums import MachineStatus


@dataclass
class Machine:
    machine_id: str
    name: str
    op_type_id: Optional[str] = None
    category: Optional[str] = None
    status: str = MachineStatus.ACTIVE.value  # active/inactive/maintain
    remark: Optional[str] = None
    team_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    op_type_ids: Tuple[str, ...] = ()

    @classmethod
    def from_row(cls, row: RowLike) -> Machine:
        op_type_id = row["op_type_id"]
        category = row["category"]
        team_id = row["team_id"]
        return cls(
            machine_id=str(row["machine_id"] or ""),
            name=str(row["name"] or ""),
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            category=str(category) if category is not None and category != "" else None,
            status=(
                str(row["status"] or MachineStatus.ACTIVE.value).strip().lower() or MachineStatus.ACTIVE.value
            ),
            remark=row["remark"],
            team_id=str(team_id) if team_id is not None and team_id != "" else None,
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            op_type_ids=tuple(row["op_type_ids"]),
        )
