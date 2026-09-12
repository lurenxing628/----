from __future__ import annotations

from datetime import datetime
from typing import Dict, Optional

from .resource_quality import MachineTypeState


def accumulate_busy_hours(
    *,
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    machine_id: str,
    operator_id: str,
    start_time: datetime,
    end_time: datetime,
) -> float:
    if not isinstance(start_time, datetime) or not isinstance(end_time, datetime):
        raise TypeError("start_time/end_time 必须是 datetime")
    duration_hours = (end_time - start_time).total_seconds() / 3600.0
    if machine_id:
        machine_busy_hours[machine_id] = float(machine_busy_hours.get(machine_id, 0.0) or 0.0) + float(duration_hours)
    if operator_id:
        operator_busy_hours[operator_id] = float(operator_busy_hours.get(operator_id, 0.0) or 0.0) + float(duration_hours)
    return float(duration_hours)


def update_machine_last_state(
    *,
    last_end_by_machine: Dict[str, datetime],
    last_op_type_by_machine: Dict[str, str],
    machine_id: str,
    end_time: datetime,
    op_type_name: Optional[str],
    seed_mode: bool,
    start_time: Optional[datetime] = None,
    op_id: Optional[int] = None,
) -> None:
    if not machine_id:
        return
    if not isinstance(end_time, datetime):
        raise TypeError("end_time 必须是 datetime")

    op_type = str(op_type_name or "").strip()
    if isinstance(last_op_type_by_machine, MachineTypeState):
        last_op_type_by_machine.record(machine_id, start_time, end_time, op_id, op_type)
    prev_end = last_end_by_machine.get(machine_id)

    if seed_mode:
        if not op_type:
            return
        if prev_end is None or end_time > prev_end:
            last_end_by_machine[machine_id] = end_time
            last_op_type_by_machine[machine_id] = op_type
        return

    # audit 2026-07-20 A16：last_op_type 必须与 last_end 同守卫——仅当机台时间线末尾
    # 真实推进时才允许覆盖上一工种。否则 gap 回填（把更早的空档排进已有更晚工序的机台）
    # 会把 (end, type) 快照改成"末尾时间不变、工种却换成回填工序"的自相矛盾状态，
    # 导致换型惩罚（internal_slot._changeover_penalty）与自动选机排序按错的上一工种计算。
    if prev_end is None or end_time > prev_end:
        last_end_by_machine[machine_id] = end_time
        if op_type:
            last_op_type_by_machine[machine_id] = op_type
