from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get


@dataclass
class OperatorMachine:
    id: Optional[int]
    operator_id: str
    machine_id: str
    skill_level: str = "normal"  # 预留：beginner/normal/skilled/expert
    is_primary: str = "no"  # yes/no（预留）
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "OperatorMachine":
        raw_id = get(row, "id")
        return cls(
            id=int(raw_id) if raw_id is not None and raw_id != "" else None,
            operator_id=str(get(row, "operator_id") or ""),
            machine_id=str(get(row, "machine_id") or ""),
            skill_level=(str(get(row, "skill_level") or "normal").strip().lower() or "normal"),
            is_primary=(str(get(row, "is_primary") or "no").strip().lower() or "no"),
            created_at=get(row, "created_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "operator_id": self.operator_id,
                "machine_id": self.machine_id,
                "skill_level": self.skill_level,
                "is_primary": self.is_primary,
                "created_at": self.created_at,
            }
        )

