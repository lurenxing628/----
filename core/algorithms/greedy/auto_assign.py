from __future__ import annotations

import math
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
    bid = str(getattr(op, "batch_id", "") or "").strip()
    prev_end = batch_progress.get(bid, base_time)
    priority = getattr(batch, "priority", None)

    fixed_machine = str(getattr(op, "machine_id", None) or "").strip()
    fixed_operator = str(getattr(op, "operator_id", None) or "").strip()
    # 防御：字段可能不是 str（例如 int），避免直接 .strip() 崩溃
    op_type_id = str(getattr(op, "op_type_id", None) or "").strip()

    # 若未固定 machine 且缺少 op_type_id，则无法保证自动选机的工种匹配
    if not fixed_machine and not op_type_id:
        return None

    machines_by_op_type = resource_pool.get("machines_by_op_type") if isinstance(resource_pool, dict) else {}
    operators_by_machine = resource_pool.get("operators_by_machine") if isinstance(resource_pool, dict) else {}
    machines_by_operator = resource_pool.get("machines_by_operator") if isinstance(resource_pool, dict) else {}
    pair_rank = resource_pool.get("pair_rank") if isinstance(resource_pool, dict) else {}

    # 防御：resource_pool.get(...) 可能返回 None（或非 dict），避免后续直接 .get 崩溃
    if not isinstance(machines_by_operator, dict):
        machines_by_operator = {}

    # 构造候选设备集合
    machine_candidates: List[str] = []
    if fixed_machine:
        machine_candidates = [fixed_machine]
    elif fixed_operator:
        machine_candidates = [str(x) for x in (machines_by_operator.get(fixed_operator) or []) if str(x).strip()]
        if not machine_candidates and isinstance(operators_by_machine, dict):
            # fallback：若未提供 machines_by_operator，则从 operators_by_machine 反推
            for mid0, oids0 in operators_by_machine.items():
                m = str(mid0).strip()
                if not m:
                    continue
                try:
                    if any(str(x).strip() == fixed_operator for x in (oids0 or [])):
                        machine_candidates.append(m)
                except Exception:
                    continue
    else:
        if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
            machine_candidates = [str(x) for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()]
        else:
            # 无 op_type_id 或映射缺失：无法保证工种匹配；宁可失败也不要“全设备兜底”排错机
            return None

    # 若已知 op_type_id：强制候选设备与工种映射一致（尤其是 fixed_operator 场景）
    if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
        allowed = {str(x).strip() for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()}
        if not allowed:
            return None
        machine_candidates = [m for m in machine_candidates if m in allowed]

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
    if not math.isfinite(float(total_hours_base)) or total_hours_base < 0:
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
            earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=oid)

            # 简化：效率取“开工时刻”的效率；若 earliest 因避让跨日/跨班次，则需重算
            def _scaled_hours(start: datetime) -> float:
                eff = 1.0
                try:
                    raw_eff = scheduler.calendar.get_efficiency(start, operator_id=oid)
                    eff = float(raw_eff) if raw_eff is not None else 1.0
                except Exception:
                    eff = 1.0
                if (not math.isfinite(float(eff))) or float(eff) <= 0:
                    eff = 1.0
                h = float(total_hours_base)
                if eff and eff > 0 and eff != 1.0:
                    return h / eff
                return h

            total_hours = _scaled_hours(earliest)

            dt_list: List[Tuple[datetime, datetime]] = []
            if machine_downtimes and mid:
                dt_list = machine_downtimes.get(mid) or []

            guard = 0
            end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=oid)
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
                earliest = scheduler.calendar.adjust_to_working_time(earliest, priority=priority, operator_id=oid)
                total_hours = _scaled_hours(earliest)
                end = scheduler.calendar.add_working_hours(earliest, total_hours, priority=priority, operator_id=oid)

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

