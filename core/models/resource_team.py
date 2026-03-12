from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get
from .enums import ResourceTeamStatus


@dataclass
class ResourceTeam:
    team_id: str
    name: str
    status: str = ResourceTeamStatus.ACTIVE.value
    remark: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ResourceTeam:
        return cls(
            team_id=str(get(row, "team_id") or ""),
            name=str(get(row, "name") or ""),
            status=(
                str(get(row, "status") or ResourceTeamStatus.ACTIVE.value).strip().lower()
                or ResourceTeamStatus.ACTIVE.value
            ),
            remark=get(row, "remark"),
            created_at=get(row, "created_at"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "team_id": self.team_id,
                "name": self.name,
                "status": self.status,
                "remark": self.remark,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
            }
        )
