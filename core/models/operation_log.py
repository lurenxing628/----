from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int


@dataclass
class OperationLog:
    id: Optional[int]
    log_time: Optional[str] = None
    log_level: str = "INFO"
    module: str = ""
    action: str = ""
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    operator: Optional[str] = None
    detail: Optional[str] = None  # JSON 字符串
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> OperationLog:
        raw_id = get(row, "id")
        return cls(
            id=parse_int(raw_id, default=None),
            log_time=get(row, "log_time"),
            log_level=str(get(row, "log_level") or "INFO"),
            module=str(get(row, "module") or ""),
            action=str(get(row, "action") or ""),
            target_type=get(row, "target_type"),
            target_id=get(row, "target_id"),
            operator=get(row, "operator"),
            detail=get(row, "detail"),
            error_code=get(row, "error_code"),
            error_message=get(row, "error_message"),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(
            {
                "id": self.id,
                "log_time": self.log_time,
                "log_level": self.log_level,
                "module": self.module,
                "action": self.action,
                "target_type": self.target_type,
                "target_id": self.target_id,
                "operator": self.operator,
                "detail": self.detail,
                "error_code": self.error_code,
                "error_message": self.error_message,
            }
        )

