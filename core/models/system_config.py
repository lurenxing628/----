from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int


@dataclass
class SystemConfig:
    id: Optional[int]
    config_key: str
    config_value: str
    description: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> "SystemConfig":
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            config_key=str(get(row, "config_key") or ""),
            config_value=str(get(row, "config_value") or ""),
            description=get(row, "description"),
            updated_at=get(row, "updated_at"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "config_key": self.config_key,
                "config_value": self.config_value,
                "description": self.description,
                "updated_at": self.updated_at,
            }
        )

