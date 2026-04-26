from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .algo_stats import increment_counter
from .internal_slot import estimate_internal_slot, validate_internal_hours


def auto_assign_internal_resources(
    scheduler: Any = None,
    *,
    calendar: Any = None,
    algo_stats: Any = None,
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
    calendar = calendar if calendar is not None else getattr(scheduler, "calendar", None)
    stats_target = algo_stats if algo_stats is not None else scheduler
    count = (lambda key: None) if probe_only else (lambda key: increment_counter(stats_target, key))
    fixed_machine, fixed_operator, op_type_id = _fixed_resource_inputs(op)

    if not fixed_machine and not op_type_id:
        count("auto_assign_missing_op_type_id_count")
        return None

    pool = _coerce_resource_pool(resource_pool)
    machine_candidates = _resolve_machine_candidates(
        fixed_machine=fixed_machine,
        fixed_operator=fixed_operator,
        op_type_id=op_type_id,
        pool=pool,
        count=count,
    )
    if not machine_candidates:
        return None

    total_hours_base = _validated_total_hours(op, batch, count=count)
    if total_hours_base is None:
        return None

    machine_candidates = _sort_machine_candidates(
        machine_candidates,
        current_type=str(getattr(op, "op_type_name", None) or "").strip(),
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
    )
    return _choose_best_pair(
        calendar=calendar,
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        pool=pool,
        fixed_operator=fixed_operator,
        machine_candidates=machine_candidates,
        total_hours_base=total_hours_base,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        count=count,
    )


def _fixed_resource_inputs(op: Any) -> Tuple[str, str, str]:
    return (
        str(getattr(op, "machine_id", None) or "").strip(),
        str(getattr(op, "operator_id", None) or "").strip(),
        str(getattr(op, "op_type_id", None) or "").strip(),
    )


def _coerce_resource_pool(resource_pool: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(resource_pool, dict):
        resource_pool = {}
    return {
        "machines_by_op_type": _dict_part(resource_pool, "machines_by_op_type"),
        "operators_by_machine": _dict_part(resource_pool, "operators_by_machine"),
        "machines_by_operator": _dict_part(resource_pool, "machines_by_operator"),
        "pair_rank": _dict_part(resource_pool, "pair_rank"),
    }


def _dict_part(source: Dict[str, Any], key: str) -> Dict[Any, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _resolve_machine_candidates(*, fixed_machine: str, fixed_operator: str, op_type_id: str, pool: Dict[str, Any], count: Any) -> List[str]:
    if fixed_machine:
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, pool=pool)
    elif op_type_id and op_type_id in pool["machines_by_op_type"]:
        candidates = [str(x) for x in (pool["machines_by_op_type"].get(op_type_id) or []) if str(x).strip()]
        if not candidates:
            count("auto_assign_missing_machine_pool_count")
            return []
    else:
        count("auto_assign_missing_machine_pool_count")
        return []
    if _needs_op_type_machine_filter(fixed_machine=fixed_machine, op_type_id=op_type_id, pool=pool):
        candidates = _filter_machines_by_op_type(candidates, op_type_id=op_type_id, pool=pool, count=count)
        if candidates is None:
            return []
    candidates = list(dict.fromkeys([mid for mid in candidates if mid]))
    if not candidates:
        count("auto_assign_no_machine_candidate_count")
    return candidates


def _machines_for_fixed_operator(fixed_operator: str, *, pool: Dict[str, Any]) -> List[str]:
    candidates = [str(x) for x in (pool["machines_by_operator"].get(fixed_operator) or []) if str(x).strip()]
    if candidates:
        return candidates
    for mid0, operator_ids in pool["operators_by_machine"].items():
        machine_id = str(mid0).strip()
        if machine_id and any(str(x).strip() == fixed_operator for x in (operator_ids or [])):
            candidates.append(machine_id)
    return candidates


def _needs_op_type_machine_filter(*, fixed_machine: str, op_type_id: str, pool: Dict[str, Any]) -> bool:
    return bool(op_type_id and (not fixed_machine or op_type_id in pool["machines_by_op_type"]))


def _filter_machines_by_op_type(candidates: List[str], *, op_type_id: str, pool: Dict[str, Any], count: Any) -> Optional[List[str]]:
    if not op_type_id:
        return candidates
    allowed = {str(x).strip() for x in (pool["machines_by_op_type"].get(op_type_id) or []) if str(x).strip()}
    if not allowed:
        count("auto_assign_missing_machine_pool_count")
        return None
    return [mid for mid in candidates if mid in allowed]


def _validated_total_hours(op: Any, batch: Any, *, count: Any) -> Optional[float]:
    try:
        return validate_internal_hours(op, batch)
    except ValueError:
        count("auto_assign_invalid_total_hours_count")
        return None


def _sort_machine_candidates(
    candidates: List[str],
    *,
    current_type: str,
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
) -> List[str]:
    return sorted(
        candidates,
        key=lambda mid: (
            0 if (current_type and (str(last_op_type_by_machine.get(mid) or "").strip() == current_type)) else 1,
            float(machine_busy_hours.get(mid, 0.0) or 0.0),
            mid,
        ),
    )


def _choose_best_pair(
    *,
    calendar: Any,
    op: Any,
    batch: Any,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    pool: Dict[str, Any],
    fixed_operator: str,
    machine_candidates: List[str],
    total_hours_base: float,
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    count: Any,
) -> Optional[Tuple[str, str]]:
    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None
    seen_operator = False
    prev_end = batch_progress.get(str(getattr(op, "batch_id", "") or "").strip(), base_time)
    for machine_id in machine_candidates:
        operator_candidates = _operator_candidates_for_machine(machine_id, fixed_operator=fixed_operator, pool=pool)
        if not operator_candidates:
            continue
        seen_operator = True
        for operator_id in _sort_operator_candidates(operator_candidates, machine_id=machine_id, pool=pool, operator_busy_hours=operator_busy_hours):
            score = _pair_score(
                calendar=calendar,
                op=op,
                batch=batch,
                machine_id=machine_id,
                operator_id=operator_id,
                base_time=base_time,
                prev_end=prev_end,
                machine_timeline=machine_timeline,
                operator_timeline=operator_timeline,
                end_dt_exclusive=end_dt_exclusive,
                machine_downtimes=machine_downtimes,
                last_op_type_by_machine=last_op_type_by_machine,
                machine_busy_hours=machine_busy_hours,
                operator_busy_hours=operator_busy_hours,
                total_hours_base=total_hours_base,
                pool=pool,
                abort_after=best[0] if best is not None else None,
            )
            if score is not None and (best is None or score < best):
                best = score
                best_pair = (machine_id, operator_id)
    if best_pair is None:
        count("auto_assign_no_operator_candidate_count" if not seen_operator else "auto_assign_no_feasible_pair_count")
    return best_pair


def _operator_candidates_for_machine(machine_id: str, *, fixed_operator: str, pool: Dict[str, Any]) -> List[str]:
    qualified = [str(x) for x in (pool["operators_by_machine"].get(machine_id) or []) if str(x).strip()]
    if not fixed_operator:
        return qualified
    return [fixed_operator] if fixed_operator in qualified else []


def _sort_operator_candidates(
    candidates: List[str],
    *,
    machine_id: str,
    pool: Dict[str, Any],
    operator_busy_hours: Dict[str, float],
) -> List[str]:
    return sorted(candidates, key=lambda oid: (_pair_rank(pool, oid, machine_id), float(operator_busy_hours.get(oid, 0.0) or 0.0), oid))


def _pair_score(
    *,
    calendar: Any,
    op: Any,
    batch: Any,
    machine_id: str,
    operator_id: str,
    base_time: datetime,
    prev_end: datetime,
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    total_hours_base: float,
    pool: Dict[str, Any],
    abort_after: Optional[datetime],
) -> Optional[Tuple[Any, ...]]:
    estimate = estimate_internal_slot(
        calendar=calendar,
        op=op,
        batch=batch,
        machine_id=machine_id,
        operator_id=operator_id,
        base_time=base_time,
        prev_end=prev_end,
        machine_timeline=machine_timeline.get(machine_id) or [],
        operator_timeline=operator_timeline.get(operator_id) or [],
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=(machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else [],
        last_op_type_by_machine=last_op_type_by_machine,
        abort_after=abort_after,
        total_hours_base=total_hours_base,
    )
    if estimate.abort_after_hit or estimate.blocked_by_window:
        return None
    load_penalty = float(machine_busy_hours.get(machine_id, 0.0) or 0.0) + float(operator_busy_hours.get(operator_id, 0.0) or 0.0)
    return (estimate.end_time, int(estimate.changeover_penalty), float(load_penalty), _pair_rank(pool, operator_id, machine_id), machine_id, operator_id)


def _pair_rank(pool: Dict[str, Any], operator_id: str, machine_id: str) -> int:
    try:
        return int(pool["pair_rank"].get((operator_id, machine_id), 9999))
    except Exception:
        return 9999
