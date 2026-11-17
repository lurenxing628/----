"""Internal exact-work witness, deliberately not a public allow-zero flag."""

from dataclasses import dataclass, fields
from datetime import datetime
from typing import Optional, Protocol

from core.shared.strict_parse import is_stored_number

from .types import ScheduleResult

_RESULT_FIELDS = tuple(f.name for f in fields(ScheduleResult))


def is_point_work(source, setup_hours, unit_hours, target_quantity):
    """Internal work with zero setup and zero unit hours over a stored target quantity: a point event."""
    return (
        source == "internal"
        and is_stored_number(setup_hours)
        and is_stored_number(unit_hours)
        and is_stored_number(target_quantity, integer=True)
        and setup_hours == 0
        and unit_hours == 0
    )


class ArrangementRow(Protocol):
    """The arrangement a point witness compares: ScheduleResult rows and validated stored rows both carry it."""

    @property
    def op_id(self) -> int: ...

    @property
    def machine_id(self) -> Optional[str]: ...

    @property
    def operator_id(self) -> Optional[str]: ...

    @property
    def start_time(self) -> datetime: ...

    @property
    def end_time(self) -> datetime: ...

    @property
    def source(self) -> str: ...


@dataclass(frozen=True)
class SchedulePointEvidence:
    op_id: int
    machine_id: str
    operator_id: str
    at: datetime
    setup_hours: float
    unit_hours: float
    quantity: int

    def matches(self, row: ArrangementRow):
        return (type(self.op_id) is int and self.op_id > 0
                and is_point_work(row.source, self.setup_hours, self.unit_hours, self.quantity)
                and isinstance(self.at, datetime) and self.at.tzinfo is None
                and all(type(key) is str and bool(key.strip())
                        for key in (self.machine_id, self.operator_id))
                and row.op_id == self.op_id
                and row.start_time == row.end_time == self.at
                and row.machine_id == self.machine_id and row.operator_id == self.operator_id)


def verified_point(row, validator):
    evidence = validator(row)
    return type(evidence) is SchedulePointEvidence and evidence.matches(row)


class PointSeedResult(ScheduleResult):
    # Internal witness is deliberately absent from dataclass/JSON fields.
    def __init__(self, result, evidence):
        super().__init__(**{name: getattr(result, name) for name in _RESULT_FIELDS})
        if type(evidence) is not SchedulePointEvidence or not evidence.matches(self):
            raise ValueError("Invalid point seed witness")
        self._point_evidence = evidence


def point_seed_valid(result):
    return (type(result) is PointSeedResult and type(result._point_evidence) is SchedulePointEvidence
            and result._point_evidence.matches(result))
