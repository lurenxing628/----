from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ._helpers import RowLike, as_dict, get, parse_int

DRAFT_STATUS_EDITING = "editing"
DRAFT_STATUS_VALIDATED = "validated"
DRAFT_STATUS_SAVED_SCENARIO = "saved_scenario"
DRAFT_STATUS_DISCARDED = "discarded"
DRAFT_STATUS_PUBLISHED = "published"
DRAFT_STATUS_EXPIRED = "expired"

VALID_DRAFT_STATUSES = (
    DRAFT_STATUS_EDITING,
    DRAFT_STATUS_VALIDATED,
    DRAFT_STATUS_SAVED_SCENARIO,
    DRAFT_STATUS_DISCARDED,
    DRAFT_STATUS_PUBLISHED,
    DRAFT_STATUS_EXPIRED,
)

CHANGE_TYPE_MOVE_TIME = "move_time"
CHANGE_TYPE_RESIZE_TIME = "resize_time"
CHANGE_TYPE_CHANGE_RESOURCE = "change_resource"

VALID_CHANGE_TYPES = (
    CHANGE_TYPE_MOVE_TIME,
    CHANGE_TYPE_RESIZE_TIME,
    CHANGE_TYPE_CHANGE_RESOURCE,
)

VALIDATION_STATUS_PENDING = "pending"
VALIDATION_STATUS_VALID = "valid"
VALIDATION_STATUS_WARNING = "warning"
VALIDATION_STATUS_BLOCKED = "blocked"

VALID_CHANGE_VALIDATION_STATUSES = (
    VALIDATION_STATUS_PENDING,
    VALIDATION_STATUS_VALID,
    VALIDATION_STATUS_WARNING,
    VALIDATION_STATUS_BLOCKED,
)


def _text_or_none(value: Any) -> Optional[str]:
    if value is None or value == "":
        return None
    return str(value)


@dataclass
class ScheduleAdjustmentDraft:
    draft_id: str
    base_version: int
    base_plan_role: str
    status: str = DRAFT_STATUS_EDITING
    created_by: Optional[str] = None
    reason: Optional[str] = None
    change_count: int = 0
    audit_summary: Optional[str] = None
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleAdjustmentDraft:
        return cls(
            draft_id=str(get(row, "draft_id") or ""),
            base_version=parse_int(get(row, "base_version"), default=0) or 0,
            base_plan_role=str(get(row, "base_plan_role") or ""),
            status=str(get(row, "status") or DRAFT_STATUS_EDITING),
            created_by=_text_or_none(get(row, "created_by")),
            reason=_text_or_none(get(row, "reason")),
            change_count=parse_int(get(row, "change_count"), default=0) or 0,
            audit_summary=_text_or_none(get(row, "audit_summary")),
            expires_at=_text_or_none(get(row, "expires_at")),
            created_at=_text_or_none(get(row, "created_at")),
            updated_at=_text_or_none(get(row, "updated_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)


@dataclass
class ScheduleAdjustmentChange:
    id: Optional[int]
    draft_id: str
    op_id: int
    change_type: str
    schedule_id: Optional[int] = None
    from_start: Optional[str] = None
    from_end: Optional[str] = None
    to_start: Optional[str] = None
    to_end: Optional[str] = None
    from_machine_id: Optional[str] = None
    to_machine_id: Optional[str] = None
    from_operator_id: Optional[str] = None
    to_operator_id: Optional[str] = None
    validation_status: str = VALIDATION_STATUS_PENDING
    validation_message: Optional[str] = None
    created_at: Optional[str] = None

    @classmethod
    def from_row(cls, row: RowLike) -> ScheduleAdjustmentChange:
        return cls(
            id=parse_int(get(row, "id"), default=None),
            draft_id=str(get(row, "draft_id") or ""),
            schedule_id=parse_int(get(row, "schedule_id"), default=None),
            op_id=parse_int(get(row, "op_id"), default=0) or 0,
            change_type=str(get(row, "change_type") or ""),
            from_start=_text_or_none(get(row, "from_start")),
            from_end=_text_or_none(get(row, "from_end")),
            to_start=_text_or_none(get(row, "to_start")),
            to_end=_text_or_none(get(row, "to_end")),
            from_machine_id=_text_or_none(get(row, "from_machine_id")),
            to_machine_id=_text_or_none(get(row, "to_machine_id")),
            from_operator_id=_text_or_none(get(row, "from_operator_id")),
            to_operator_id=_text_or_none(get(row, "to_operator_id")),
            validation_status=str(get(row, "validation_status") or VALIDATION_STATUS_PENDING),
            validation_message=_text_or_none(get(row, "validation_message")),
            created_at=_text_or_none(get(row, "created_at")),
        )

    def to_dict(self) -> Dict[str, Any]:
        return as_dict(self.__dict__)
