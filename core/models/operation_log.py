from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ._helpers import RowLike, parse_optional_int


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
        log_level = str(row["log_level"] or "").strip()
        if not log_level:
            raise ValueError("OperationLogs.log_level cannot be empty")
        return cls(
            id=parse_optional_int(row["id"], field="id"),
            log_time=row["log_time"],
            log_level=log_level,
            module=str(row["module"]),
            action=str(row["action"]),
            target_type=row["target_type"],
            target_id=row["target_id"],
            operator=row["operator"],
            detail=row["detail"],
            error_code=row["error_code"],
            error_message=row["error_message"],
        )
