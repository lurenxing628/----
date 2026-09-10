"""Internal exact-work witness, deliberately not a public allow-zero flag."""

import math
from dataclasses import asdict, dataclass
from datetime import datetime

from .types import ScheduleResult


@dataclass(frozen=True)
class SchedulePointEvidence:
    op_id: int
    machine_id: str
    operator_id: str
    at: datetime
    setup_hours: float
    unit_hours: float
    quantity: int

    def matches(self, row):
        values = (self.setup_hours, self.unit_hours, self.quantity)
        return (type(self.op_id) is int and self.op_id > 0
                and type(self.quantity) is int and self.quantity >= 0
                and all(type(value) in (int, float) and 0 <= value <= 9007199254740991
                        and math.isfinite(value) for value in values)
                and self.setup_hours == 0 and (self.unit_hours == 0 or self.quantity == 0)
                and isinstance(self.at, datetime) and self.at.tzinfo is None and self.at.microsecond == 0
                and all(type(key) is str and key and key.strip() == key
                        for key in (self.machine_id, self.operator_id))
                and row.source == "internal" and row.op_id == self.op_id
                and row.start_time == row.end_time == self.at
                and row.machine_id == self.machine_id and row.operator_id == self.operator_id)


def verified_point(row, validator):
    if not callable(validator):
        return False
    evidence = validator(row)
    return type(evidence) is SchedulePointEvidence and evidence.matches(row)


class PointSeedResult(ScheduleResult):
    # Internal witness is deliberately absent from dataclass/JSON fields.
    def __init__(self, result, evidence):
        super().__init__(**asdict(result))
        if type(evidence) is not SchedulePointEvidence or not evidence.matches(self):
            raise ValueError("Invalid point seed witness")
        self._point_evidence = evidence


def point_seed_valid(result):
    return (type(result) is PointSeedResult and type(result._point_evidence) is SchedulePointEvidence
            and result._point_evidence.matches(result))
