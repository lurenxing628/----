from __future__ import annotations

from typing import Optional, TypedDict


class ScheduleTimeSpanRow(TypedDict):
    version: int
    start_time: str
    end_time: str
    end_includes_point: bool


class ScheduleDetailRow(TypedDict):
    task_ref: str
    op_id: int
    operation_ref: str
    start_time: str
    end_time: str
    start_us: int
    end_us: int
    is_point_event: int
    op_code: str
    batch_id: str
    op_type_name: str
    source: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    machine_name: Optional[str]
    operator_name: Optional[str]
