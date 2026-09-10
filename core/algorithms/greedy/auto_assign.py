from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, NamedTuple, Optional, Tuple

from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.auto_assign_contract import (
    AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS,
    AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL,
    AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID,
    AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR,
    AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE,
    AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE,
    AUTO_ASSIGN_REASON_SUCCESS,
    AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
    AutoAssignAttempt,
    auto_assign_attempt_from_result,
)
from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithm_runtime.slot_overlap_reuse import overlap_reuse_for
from core.infrastructure.errors import ValidationError
from core.shared.strict_parse import parse_required_int


@dataclass(frozen=True)
class _MachineCandidates:
    values: List[str]
    reason: str = AUTO_ASSIGN_REASON_SUCCESS


class _PairProbe(NamedTuple):
    """单个机-人组合的评估结果：score=None 表示不可行，window_blocked 标记不可行原因是否为窗口截止。"""

    score: Optional[Tuple[Any, ...]]
    window_blocked: bool


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
    attempt = auto_assign_internal_resources_attempt(
        scheduler=scheduler,
        calendar=calendar,
        algo_stats=algo_stats,
        op=op,
        batch=batch,
        batch_progress=batch_progress,
        machine_timeline=machine_timeline,
        operator_timeline=operator_timeline,
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        machine_downtimes=machine_downtimes,
        resource_pool=resource_pool,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        probe_only=probe_only,
    )
    if attempt.machine_id and attempt.operator_id:
        return attempt.machine_id, attempt.operator_id
    return None


def auto_assign_internal_resources_attempt(
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
) -> AutoAssignAttempt:
    calendar = calendar if calendar is not None else getattr(scheduler, "calendar", None)
    stats_target = algo_stats if algo_stats is not None else scheduler
    count = (lambda key: None) if probe_only else (lambda key: increment_counter(stats_target, key))
    fixed_machine, fixed_operator, op_type_id = _fixed_resource_inputs(op)

    if not fixed_machine and not op_type_id:
        count("auto_assign_missing_op_type_id_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID)

    pool = _coerce_resource_pool(resource_pool)
    machine_choice = _resolve_machine_candidates(
        fixed_machine=fixed_machine,
        fixed_operator=fixed_operator,
        op_type_id=op_type_id,
        pool=pool,
        count=count,
    )
    if not machine_choice.values:
        return AutoAssignAttempt(reason=machine_choice.reason)

    total_hours_base = _validated_total_hours(op, batch, count=count)
    if total_hours_base is None:
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS)

    machine_candidates = _sort_machine_candidates(
        machine_choice.values,
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


def _resolve_machine_candidates(
    *,
    fixed_machine: str,
    fixed_operator: str,
    op_type_id: str,
    pool: Dict[str, Any],
    count: Any,
) -> _MachineCandidates:
    if fixed_machine:
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, pool=pool)
    elif op_type_id and op_type_id in pool["machines_by_op_type"]:
        candidates = [str(x) for x in (pool["machines_by_op_type"].get(op_type_id) or []) if str(x).strip()]
        if not candidates:
            count("auto_assign_missing_machine_pool_count")
            return _MachineCandidates([], AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL)
    else:
        count("auto_assign_missing_machine_pool_count")
        return _MachineCandidates([], AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL)
    if _needs_op_type_machine_filter(fixed_machine=fixed_machine, op_type_id=op_type_id, pool=pool):
        candidates = _filter_machines_by_op_type(candidates, op_type_id=op_type_id, pool=pool, count=count)
        if candidates is None:
            return _MachineCandidates([], AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL)
    candidates = list(dict.fromkeys([mid for mid in candidates if mid]))
    if not candidates:
        count("auto_assign_no_machine_candidate_count")
        return _MachineCandidates([], AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE)
    return _MachineCandidates(candidates)


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
) -> AutoAssignAttempt:
    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None
    seen_operator = False
    window_blocked_pairs = 0
    non_window_infeasible_pairs = 0
    prev_end = batch_progress.get(str(getattr(op, "batch_id", "") or "").strip(), base_time)
    for machine_id in machine_candidates:
        operator_candidates = _operator_candidates_for_machine(machine_id, fixed_operator=fixed_operator, pool=pool)
        if not operator_candidates:
            continue
        seen_operator = True
        for operator_id in _sort_operator_candidates(operator_candidates, machine_id=machine_id, pool=pool, operator_busy_hours=operator_busy_hours):
            probe = _pair_score(
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
            if probe.score is not None:
                if best is None or probe.score < best:
                    best = probe.score
                    best_pair = (machine_id, operator_id)
            elif probe.window_blocked:
                window_blocked_pairs += 1
            else:
                non_window_infeasible_pairs += 1
    if best_pair is None:
        return _pair_failure_attempt(
            seen_operator=seen_operator,
            window_blocked_pairs=window_blocked_pairs,
            non_window_infeasible_pairs=non_window_infeasible_pairs,
            count=count,
        )
    return AutoAssignAttempt(machine_id=best_pair[0], operator_id=best_pair[1])


def _pair_failure_attempt(
    *,
    seen_operator: bool,
    window_blocked_pairs: int,
    non_window_infeasible_pairs: int,
    count: Any,
) -> AutoAssignAttempt:
    if not seen_operator:
        count("auto_assign_no_operator_candidate_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE)
    # 窗口归因规则：仅当"所有被评估的机-人组合都因排产截止窗口被拒、且不存在窗口外原因的
    # 不可行判定"时才归因 WINDOW_BLOCKED；混合场景（存在窗口外原因的不可行判定）保持
    # NO_FEASIBLE_PAIR，宁可保守也不把非窗口问题伪装成截止日期问题。
    # 注：abort_after 剪枝（非窗口 None）只会在已找到可行 best 后出现，走不到这里，
    # 这里对它的计数纯属防御。
    if window_blocked_pairs > 0 and non_window_infeasible_pairs == 0:
        count("auto_assign_window_blocked_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED)
    count("auto_assign_no_feasible_pair_count")
    return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR)


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
) -> _PairProbe:
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
        overlap_reuse=overlap_reuse_for(machine_timeline),
    )
    if estimate.abort_after_hit:
        return _PairProbe(score=None, window_blocked=False)
    if estimate.blocked_by_window:
        return _PairProbe(score=None, window_blocked=True)
    load_penalty = float(machine_busy_hours.get(machine_id, 0.0) or 0.0) + float(operator_busy_hours.get(operator_id, 0.0) or 0.0)
    return _PairProbe(
        score=(estimate.end_time, int(estimate.changeover_penalty), float(load_penalty), _pair_rank(pool, operator_id, machine_id), machine_id, operator_id),
        window_blocked=False,
    )


def _pair_rank(pool: Dict[str, Any], operator_id: str, machine_id: str) -> int:
    pair = (operator_id, machine_id)
    if pair not in pool["pair_rank"]:
        return 9999
    try:
        return parse_required_int(pool["pair_rank"][pair], field="pair_rank")
    except ValidationError as exc:
        raise ValidationError(f"pair_rank 必须是整数：operator_id={operator_id!r} machine_id={machine_id!r}", field="pair_rank") from exc
