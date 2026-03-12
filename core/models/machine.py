from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get
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

    @classmethod
    def from_row(cls, row: RowLike) -> Machine:
        op_type_id = get(row, "op_type_id")
        category = get(row, "category")
        team_id = get(row, "team_id")
        return cls(
            machine_id=str(get(row, "machine_id") or ""),
            name=str(get(row, "name") or ""),
            op_type_id=str(op_type_id) if op_type_id is not None and op_type_id != "" else None,
            category=str(category) if category is not None and category != "" else None,
            status=(
                str(get(row, "status") or MachineStatus.ACTIVE.value).strip().lower() or MachineStatus.ACTIVE.value
            ),
            remark=get(row, "remark"),
            team_id=str(team_id) if team_id is not None and team_id != "" else None,
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
                "team_id": self.team_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )
