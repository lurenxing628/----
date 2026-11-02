"""Shared positive internal resource occupancy projection for runtime state, evaluation, and capacity."""

from __future__ import annotations

from datetime import datetime
from typing import NamedTuple, Optional, Tuple

from .ordering import clean_resource_id
from .types import ScheduleResult
from .value_domains import INTERNAL


class ResourceOccupancy(NamedTuple):
    op_id: int
    op_type_id: Optional[str]
    start_time: datetime
    end_time: datetime
    machine_id: str
    operator_id: str


class PreparedSeedApplication(NamedTuple):
    result: ScheduleResult
    occupancies: Tuple[ResourceOccupancy, ...]


def project_internal_occupancies(
    result: ScheduleResult,
    *,
    actual_segments: Tuple[Tuple[datetime, datetime, str, str], ...] = (),
) -> Tuple[ResourceOccupancy, ...]:
    if result.source != INTERNAL:
        return ()
    if actual_segments:
        return tuple(
            ResourceOccupancy(
                op_id=result.op_id,
                op_type_id=result.op_type_id,
                start_time=start,
                end_time=end,
                machine_id=clean_resource_id(machine),
                operator_id=clean_resource_id(operator),
            )
            for start, end, machine, operator in actual_segments
        )
    if result.end_time > result.start_time:
        return (
            ResourceOccupancy(
                op_id=result.op_id,
                op_type_id=result.op_type_id,
                start_time=result.start_time,
                end_time=result.end_time,
                machine_id=clean_resource_id(result.machine_id),
                operator_id=clean_resource_id(result.operator_id),
            ),
        )
    return ()


__all__ = [
    "PreparedSeedApplication",
    "ResourceOccupancy",
    "project_internal_occupancies",
]
