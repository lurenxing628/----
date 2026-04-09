from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .algo_stats import increment_counter
from .internal_slot import estimate_internal_slot, validate_internal_hours


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
    probe_only: bool = False,
) -> Optional[Tuple[str, str]]:
    """
    内部工序缺省资源时，自动选择 (machine_id, operator_id)。

    选择目标（简化的多目标）：
    1) 预计完工时间最早（end 最小）
    2) 尽量不换型（同一设备连续 op_type_name 相同优先）
    3) 负荷均衡（优先选择当前更空闲的人/机）
    4) 若存在主操/高技能标记（pair_rank 更小），作为微弱 tie-break
    """
    _count = increment_counter if not probe_only else (lambda *_args, **_kwargs: None)

    bid = str(getattr(op, "batch_id", "") or "").strip()
    prev_end = batch_progress.get(bid, base_time)

    fixed_machine = str(getattr(op, "machine_id", None) or "").strip()
    fixed_operator = str(getattr(op, "operator_id", None) or "").strip()
    op_type_id = str(getattr(op, "op_type_id", None) or "").strip()

    if not fixed_machine and not op_type_id:
        _count(scheduler, "auto_assign_missing_op_type_id_count")
        return None

    machines_by_op_type = resource_pool.get("machines_by_op_type") if isinstance(resource_pool, dict) else {}
    operators_by_machine = resource_pool.get("operators_by_machine") if isinstance(resource_pool, dict) else {}
    machines_by_operator = resource_pool.get("machines_by_operator") if isinstance(resource_pool, dict) else {}
    pair_rank = resource_pool.get("pair_rank") if isinstance(resource_pool, dict) else {}

    if not isinstance(machines_by_operator, dict):
        machines_by_operator = {}

    machine_candidates: List[str] = []
    if fixed_machine:
        machine_candidates = [fixed_machine]
    elif fixed_operator:
        machine_candidates = [str(x) for x in (machines_by_operator.get(fixed_operator) or []) if str(x).strip()]
        if not machine_candidates and isinstance(operators_by_machine, dict):
            for mid0, operator_ids in operators_by_machine.items():
                machine_id = str(mid0).strip()
                if not machine_id:
                    continue
                if any(str(x).strip() == fixed_operator for x in (operator_ids or [])):
                    machine_candidates.append(machine_id)
    else:
        if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
            machine_candidates = [str(x) for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()]
        else:
            _count(scheduler, "auto_assign_missing_machine_pool_count")
            return None

    if op_type_id and isinstance(machines_by_op_type, dict) and op_type_id in machines_by_op_type:
        allowed = {str(x).strip() for x in (machines_by_op_type.get(op_type_id) or []) if str(x).strip()}
        if not allowed:
            _count(scheduler, "auto_assign_missing_machine_pool_count")
            return None
        machine_candidates = [mid for mid in machine_candidates if mid in allowed]

    machine_candidates = list(dict.fromkeys([mid for mid in machine_candidates if mid]))
    if not machine_candidates:
        _count(scheduler, "auto_assign_no_machine_candidate_count")
        return None

    try:
        total_hours_base = validate_internal_hours(op, batch)
    except ValueError:
        _count(scheduler, "auto_assign_invalid_total_hours_count")
        return None

    current_type = str(getattr(op, "op_type_name", None) or "").strip()
    machine_candidates = sorted(
        machine_candidates,
        key=lambda mid: (
            0 if (current_type and (str(last_op_type_by_machine.get(mid) or "").strip() == current_type)) else 1,
            float(machine_busy_hours.get(mid, 0.0) or 0.0),
            mid,
        ),
    )

    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None
    seen_operator_candidate = False

    for mid in machine_candidates:
        if isinstance(operators_by_machine, dict):
            qualified = [str(x) for x in (operators_by_machine.get(mid) or []) if str(x).strip()]
        else:
            qualified = []

        if fixed_operator:
            if fixed_operator not in qualified:
                continue
            operator_candidates = [fixed_operator]
        else:
            operator_candidates = qualified

        if not operator_candidates:
            continue
        seen_operator_candidate = True
        operator_candidates = sorted(
            operator_candidates,
            key=lambda oid: (
                int((pair_rank or {}).get((oid, mid), 9999)) if isinstance(pair_rank, dict) else 9999,
                float(operator_busy_hours.get(oid, 0.0) or 0.0),
                oid,
            ),
        )

        for oid in operator_candidates:
            estimate = estimate_internal_slot(
                calendar=scheduler.calendar,
                op=op,
                batch=batch,
                machine_id=mid,
                operator_id=oid,
                base_time=base_time,
                prev_end=prev_end,
                machine_timeline=machine_timeline.get(mid) or [],
                operator_timeline=operator_timeline.get(oid) or [],
                end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=(machine_downtimes.get(mid) or []) if machine_downtimes and mid else [],
                last_op_type_by_machine=last_op_type_by_machine,
                abort_after=(best[0] if best is not None else None),
                total_hours_base=total_hours_base,
            )
            if estimate.abort_after_hit or estimate.blocked_by_window:
                continue

            load_penalty = float(machine_busy_hours.get(mid, 0.0) or 0.0) + float(operator_busy_hours.get(oid, 0.0) or 0.0)
            try:
                rank = int((pair_rank or {}).get((oid, mid), 9999))
            except Exception:
                rank = 9999

            score = (
                estimate.end_time,
                int(estimate.changeover_penalty),
                float(load_penalty),
                int(rank),
                mid,
                oid,
            )
            if best is None or score < best:
                best = score
                best_pair = (mid, oid)

    if best_pair is None:
        if not seen_operator_candidate:
            _count(scheduler, "auto_assign_no_operator_candidate_count")
        else:
            _count(scheduler, "auto_assign_no_feasible_pair_count")

    return best_pair
