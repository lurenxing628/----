from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, get
from .enums import OperatorStatus


@dataclass
class Operator:
    operator_id: str
    name: str
    status: str = OperatorStatus.ACTIVE.value  # active/inactive
    remark: Optional[str] = None
    team_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> Operator:
        team_id = get(row, "team_id")
        return cls(
            operator_id=str(get(row, "operator_id") or ""),
            name=str(get(row, "name") or ""),
            status=(
                str(get(row, "status") or OperatorStatus.ACTIVE.value).strip().lower()
                or OperatorStatus.ACTIVE.value
            ),
            remark=get(row, "remark"),
            team_id=str(team_id) if team_id is not None and team_id != "" else None,
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )
