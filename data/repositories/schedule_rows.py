from __future__ import annotations

from typing import Optional, TypedDict


class ScheduleSeedRow(TypedDict, total=False):
    op_id: int
    machine_id: Optional[str]
    operator_id: Optional[str]
    start_time: str
    end_time: str


class ScheduleTimeSpanRow(TypedDict, total=False):
    version: int
    start_time: str
    end_time: str


class ScheduleDetailRow(TypedDict, total=False):
    schedule_id: int
    op_id: int
    start_time: str
    end_time: str
    lock_status: str
    version: int
    op_code: str
    batch_id: str
    piece_id: Optional[str]
    seq: int
    op_type_name: str
    source: str
    op_status: str
    machine_id: Optional[str]
    operator_id: Optional[str]
    supplier_id: Optional[str]
    part_no: Optional[str]
    part_name: Optional[str]
    due_date: Optional[str]
    priority: Optional[str]
    machine_name: Optional[str]
    operator_name: Optional[str]
    supplier_name: Optional[str]


class ScheduleDispatchRow(ScheduleDetailRow, total=False):
    machine_team_id: Optional[str]
    machine_team_name: Optional[str]
    operator_team_id: Optional[str]
    operator_team_name: Optional[str]
