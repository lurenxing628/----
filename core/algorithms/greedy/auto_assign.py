from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .downtime import find_overlap_shift_end


def auto_assign_internal_resources(
    scheduler: Any,
    *,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    resource_pool: Dict[str, Any],
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
) -> Optional[Tuple[str, str]]:
    """
    内部工序缺省资源时，自动选择 (machine_id, operator_id)。

    选择目标（简化的多目标）：
    1) 预计完工时间最早（end 最小）
    2) 尽量不换型（同一设备连续 op_type_name 相同优先）
    3) 负荷均衡（优先选择当前更空闲的人/机）
    4) 若存在主操/高技能标记（pair_rank 更小），作为微弱 tie-break
    """
    bid = str(getattr(op, "batch_id", "") or "")
    prev_end = batch_progress.get(bid, base_time)
    priority = getattr(batch, "priority", None)

    fixed_machine = (getattr(op, "machine_id", None) or "").strip()
    fixed_operator = (getattr(op, "operator_id", None) or "").strip()
    op_type_id = (getattr(op, "op_type_id", None) or "").strip()

    machines_by_op_type = resource_pool.get("machines_by_op_type") if isinstance(resource_pool, dict) else {}
    operators_by_machine = resource_pool.get("operators_by_machine") if isinstance(resource_pool, dict) else {}
    machines_by_operator = resource_pool.get("machines_by_operator") if isinstance(resource_pool, dict) else {}
    pair_rank = resource_pool.get("pair_rank") if isinstance(resource_pool, dict) else {}

    # 构造候选设备集合
    machine_candidates: List[str] = []
    if fixed_machine:
        machine_candidates = [fixed_machine]
    elif fixed_operator:
        machine_candidates = [str(x) for x in (machines_by_operator.get(fixed_operator) or []) if str(x).strip()]
    else:
        if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
            machine_candidates = [str(x) for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()]
        else:
            # 无 op_type_id 或映射缺失：退化为“所有可用设备”
            if isinstance(operators_by_machine, dict):
                machine_candidates = [str(x) for x in operators_by_machine.keys() if str(x).strip()]

    # 去重 + 稳定
    machine_candidates = sorted(list({m for m in machine_candidates if m}), key=lambda x: x)
    if not machine_candidates:
        return None

    # 工时
    setup_hours = getattr(op, "setup_hours", 0) or 0
    unit_hours = getattr(op, "unit_hours", 0) or 0
    qty = getattr(batch, "quantity", 0) or 0
    try:
        total_hours_base = float(setup_hours) + float(unit_hours) * float(qty)
    except Exception:
        return None
    if total_hours_base < 0:
        return None

    cur_type = (str(getattr(op, "op_type_name", None) or "") or "").strip()

    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None

    for mid in machine_candidates:
        # 候选人员集合
        op_candidates: List[str] = []
        if isinstance(operators_by_machine, dict):
            qualified = [str(x) for x in (operators_by_machine.get(mid) or []) if str(x).strip()]
        else:
            qualified = []
        if fixed_operator:
            # 固定 operator：必须在该设备的资质列表内
            if fixed_operator not in qualified:
                continue
            op_candidates = [fixed_operator]
        else:
            op_candidates = qualified

        if not op_candidates:
            continue

        # 逐 (machine, operator) 评估可行最早区间
        for oid in op_candidates:
            earliest = max(prev_end, base_time)
            earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority)

            # 简化：效率取开工时刻对应日的效率
            total_hours = float(total_hours_base)
            try:
                eff = float(scheduler.calendar.get_efficiency(earliest) or 1.0)
            except Exception:
                eff = 1.0
            if eff and 0 < eff < 1.0:
                total_hours = total_hours / eff

            dt_list: List[Tuple[datetime, datetime]] = []
            if machine_downtimes and mid:
                dt_list = machine_downtimes.get(mid) or []

            guard = 0
            end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority)
            while guard < 200:
                guard += 1
                shift_to: Optional[datetime] = None
                m_shift = find_overlap_shift_end(machine_timeline.get(mid) or [], earliest, end)
                o_shift = find_overlap_shift_end(operator_timeline.get(oid) or [], earliest, end)
                d_shift = find_overlap_shift_end(dt_list, earliest, end)
                for x in (m_shift, o_shift, d_shift):
                    if x is None:
                        continue
                    if shift_to is None or x > shift_to:
                        shift_to = x
                if shift_to is None:
                    break
                earliest = max(earliest, shift_to)
                earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority)
                end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority)

            if guard >= 200:
                continue
            if end_dt_exclusive is not None and end >= end_dt_exclusive:
                continue

            last_type = (last_op_type_by_machine.get(mid) or "").strip()
            change_pen = 1 if (last_type and cur_type and last_type != cur_type) else 0
            load_pen = float(machine_busy_hours.get(mid, 0.0) or 0.0) + float(operator_busy_hours.get(oid, 0.0) or 0.0)
            rank = 9999
            try:
                rank = int((pair_rank or {}).get((oid, mid), 9999))
            except Exception:
                rank = 9999

            score = (end, int(change_pen), float(load_pen), int(rank), mid, oid)
            if best is None or score < best:
                best = score
                best_pair = (mid, oid)

    return best_pair

