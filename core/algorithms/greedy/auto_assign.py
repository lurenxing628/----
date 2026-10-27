from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Tuple

from core.algorithm_contracts.operator_eligibility import qualified_operators
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_runtime.algo_stats import increment_counter
from core.algorithm_runtime.auto_assign_contract import (
    AUTO_ASSIGN_REASON_MISSING_MACHINE_POOL,
    AUTO_ASSIGN_REASON_NO_MACHINE_CANDIDATE,
    AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE,
    AUTO_ASSIGN_REASON_SUCCESS,
    AUTO_ASSIGN_REASON_WINDOW_BLOCKED,
    AutoAssignAttempt,
)
from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.algorithm_runtime.resource_quality import prefer_resource_pair
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_handoff
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse, overlap_reuse_for
from core.models.batch import Batch

if TYPE_CHECKING:
    from .schedule_preparation import NativeSchedulePreparation


@dataclass(frozen=True)
class _MachineCandidates:
    values: List[str]
    reason: str = AUTO_ASSIGN_REASON_SUCCESS


@dataclass(frozen=True)
class ResourceCandidates:
    machines: Tuple[str, ...]
    fixed_operator: Optional[str]
    op_type_id: str
    pool: Dict[str, Any]
    reason: str
    counters: Tuple[str, ...]
    _operators_by_machine: Dict[str, Tuple[str, ...]] = field(default_factory=dict, init=False)
    _pairs: Optional[Tuple[Tuple[str, str], ...]] = field(default=None, init=False)
    _eligible_resources: Optional[Tuple[Tuple[str, ...], Tuple[str, ...]]] = field(default=None, init=False)

    def operators_for_machine(self, machine_id: str) -> Tuple[str, ...]:
        if machine_id not in self._operators_by_machine:
            self._operators_by_machine[machine_id] = tuple(_operator_candidates_for_machine(
                machine_id, fixed_operator=self.fixed_operator, pool=self.pool, op_type_id=self.op_type_id,
            ))
        return self._operators_by_machine[machine_id]

    @property
    def pairs(self) -> Tuple[Tuple[str, str], ...]:
        pairs = self._pairs
        if pairs is None:
            pairs = tuple((machine_id, operator_id) for machine_id in self.machines
                          for operator_id in self.operators_for_machine(machine_id))
            object.__setattr__(self, "_pairs", pairs)
        return pairs

    @property
    def eligible_resources(self) -> Optional[Tuple[Tuple[str, ...], Tuple[str, ...]]]:
        if not self.machines:
            return None
        if self._eligible_resources is None:
            operators = tuple(dict.fromkeys(operator_id for _machine_id, operator_id in self.pairs))
            object.__setattr__(self, "_eligible_resources", (self.machines, operators))
        return self._eligible_resources


def prepare_resource_candidates(op: OpForScheduleAlgo, resource_pool: Any) -> ResourceCandidates:
    fixed_machine, fixed_operator, op_type_id = fixed_resource_inputs(op)
    pool, counters = _coerce_resource_pool(resource_pool), []
    choice = _resolve_machine_candidates(fixed_machine=fixed_machine, fixed_operator=fixed_operator,
                                        op_type_id=op_type_id, pool=pool, count=counters.append)
    return ResourceCandidates(tuple(choice.values), fixed_operator, op_type_id, pool, choice.reason, tuple(counters))


def auto_assign_internal_resources_attempt(
    *,
    calendar: Any = None,
    algo_stats: Any = None,
    op: OpForScheduleAlgo,
    batch: Batch,
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
    resource_preparation: NativeSchedulePreparation,
) -> AutoAssignAttempt:
    count = (lambda key: None) if probe_only else (lambda key: increment_counter(algo_stats, key))
    candidates = resource_preparation.resource_candidates_for(op)
    for counter in candidates.counters:
        count(counter)
    if not candidates.machines:
        return AutoAssignAttempt(reason=candidates.reason)
    if resource_pool is resource_preparation.resource_pool:
        pool = candidates.pool
    else:
        pool = _coerce_resource_pool(resource_pool)
    total_hours_base = resource_preparation.total_hours_by_op_id[op.id]

    machine_candidates = _sort_machine_candidates(
        candidates.machines,
        current_type=op.op_type_name,
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
        machine_candidates=machine_candidates,
        total_hours_base=total_hours_base,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        count=count,
        static_candidates=candidates,
    )


def qualified_resource_pairs(op: OpForScheduleAlgo, resource_pool: Any) -> Tuple[Tuple[str, str], ...]:
    """The shared machine, authorization and skill rule used by assignment and repair."""
    return prepare_resource_candidates(op, resource_pool).pairs


def fixed_resource_inputs(op: OpForScheduleAlgo) -> Tuple[Optional[str], Optional[str], str]:
    # 未指定的设备或人员只拼作 None。
    return op.machine_id, op.operator_id, op.op_type_id


def _coerce_resource_pool(resource_pool: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(resource_pool, dict):
        resource_pool = {}
    return {
        "machines_by_op_type": _dict_part(resource_pool, "machines_by_op_type"),
        "operators_by_machine": _dict_part(resource_pool, "operators_by_machine"),
        "machines_by_operator": _dict_part(resource_pool, "machines_by_operator"),
        "pair_rank": _dict_part(resource_pool, "pair_rank"),
        **({"operator_skills": resource_pool["operator_skills"]} if "operator_skills" in resource_pool else {}),
    }


def _dict_part(source: Dict[str, Any], key: str) -> Dict[Any, Any]:
    value = source.get(key)
    return value if isinstance(value, dict) else {}


def _resolve_machine_candidates(
    *,
    fixed_machine: Optional[str],
    fixed_operator: Optional[str],
    op_type_id: str,
    pool: Dict[str, Any],
    count: Any,
) -> _MachineCandidates:
    if fixed_machine:
        candidates = [fixed_machine]
    elif fixed_operator:
        candidates = _machines_for_fixed_operator(fixed_operator, pool=pool)
    elif op_type_id in pool["machines_by_op_type"]:
        candidates = [str(x) for x in pool["machines_by_op_type"][op_type_id] if str(x).strip()]
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
    return [str(x) for x in (pool["machines_by_operator"].get(fixed_operator) or []) if str(x).strip()]


def _needs_op_type_machine_filter(*, fixed_machine: Optional[str], op_type_id: str, pool: Dict[str, Any]) -> bool:
    return not fixed_machine or op_type_id in pool["machines_by_op_type"]


def _filter_machines_by_op_type(candidates: List[str], *, op_type_id: str, pool: Dict[str, Any], count: Any) -> Optional[List[str]]:
    # build_resource_pool sets a list for every op type of the internal operations being scheduled.
    allowed = {str(x).strip() for x in pool["machines_by_op_type"][op_type_id] if str(x).strip()}
    if not allowed:
        count("auto_assign_missing_machine_pool_count")
        return None
    return [mid for mid in candidates if mid in allowed]


def _sort_machine_candidates(
    candidates: Iterable[str],
    *,
    current_type: str,
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
) -> List[str]:
    return sorted(
        candidates,
        key=lambda mid: (
            # Machine types are written only non-empty and stripped (runtime_state.update_machine_last_state).
            0 if last_op_type_by_machine.get(mid) == current_type else 1,
            machine_busy_hours.get(mid, 0.0),
            mid,
        ),
    )


def _choose_best_pair(
    *,
    calendar: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    batch_progress: Dict[str, datetime],
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    base_time: datetime,
    end_dt_exclusive: Optional[datetime],
    machine_downtimes: Optional[Dict[str, List[Tuple[datetime, datetime]]]],
    pool: Dict[str, Any],
    machine_candidates: List[str],
    total_hours_base: float,
    last_op_type_by_machine: Dict[str, str],
    machine_busy_hours: Dict[str, float],
    operator_busy_hours: Dict[str, float],
    count: Any,
    static_candidates: ResourceCandidates,
) -> AutoAssignAttempt:
    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None
    seen_operator = False
    tie_seen = False
    prev_end = batch_progress.get(op.batch_id, base_time)
    handoff = current_sgs_handoff()
    overlap_reuse = overlap_reuse_for(machine_timeline)
    for machine_id in machine_candidates:
        operator_candidates = static_candidates.operators_for_machine(machine_id)
        if not operator_candidates:
            continue
        seen_operator = True
        m_timeline = machine_timeline.get(machine_id, [])
        m_downtimes = (machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else []
        m_busy = machine_busy_hours.get(machine_id, 0.0)
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
                last_op_type_by_machine=last_op_type_by_machine,
                operator_busy_hours=operator_busy_hours,
                total_hours_base=total_hours_base,
                pool=pool,
                abort_after=best[0] if best is not None else None,
                handoff=handoff,
                m_timeline=m_timeline,
                m_downtimes=m_downtimes,
                m_busy=m_busy,
                overlap_reuse=overlap_reuse,
            )
            if score is not None:
                if best is not None and score[:2] == best[:2]:
                    tie_seen = True
                if best is None or prefer_resource_pair(last_op_type_by_machine, op, score, best):
                    best = score
                    best_pair = (machine_id, operator_id)
    if best_pair is None:
        return _pair_failure_attempt(
            seen_operator=seen_operator,
            count=count,
        )
    return AutoAssignAttempt(machine_id=best_pair[0], operator_id=best_pair[1], pair_tie_occurred=tie_seen)


def _pair_failure_attempt(
    *,
    seen_operator: bool,
    count: Any,
) -> AutoAssignAttempt:
    if not seen_operator:
        count("auto_assign_no_operator_candidate_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE, pair_tie_occurred=False)
    count("auto_assign_window_blocked_count")
    return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED, pair_tie_occurred=False)


def _operator_candidates_for_machine(machine_id: str, *, fixed_operator: Optional[str], pool: Dict[str, Any], op_type_id: str) -> List[str]:
    qualified = [str(x) for x in (pool["operators_by_machine"].get(machine_id) or []) if str(x).strip()]
    qualified = qualified_operators(pool, qualified, op_type_id)
    if not fixed_operator:
        return qualified
    return [fixed_operator] if fixed_operator in qualified else []


def _sort_operator_candidates(
    candidates: Iterable[str],
    *,
    machine_id: str,
    pool: Dict[str, Any],
    operator_busy_hours: Dict[str, float],
) -> List[str]:
    return sorted(candidates, key=lambda oid: (_pair_rank(pool, oid, machine_id), operator_busy_hours.get(oid, 0.0), oid))


def _pair_score(
    *,
    calendar: Any,
    op: OpForScheduleAlgo,
    batch: Batch,
    machine_id: str,
    operator_id: str,
    base_time: datetime,
    prev_end: datetime,
    machine_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    operator_timeline: Dict[str, List[Tuple[datetime, datetime]]],
    end_dt_exclusive: Optional[datetime],
    last_op_type_by_machine: Dict[str, str],
    operator_busy_hours: Dict[str, float],
    total_hours_base: float,
    pool: Dict[str, Any],
    abort_after: Optional[datetime],
    handoff: Any,
    m_timeline: List[Tuple[datetime, datetime]],
    m_downtimes: List[Tuple[datetime, datetime]],
    m_busy: float,
    overlap_reuse: Optional[SlotOverlapReuse],
) -> Optional[Tuple[Any, ...]]:
    def estimate_pair(abort_at: Optional[datetime]):
        return estimate_internal_slot(
            calendar=calendar,
            op=op,
            batch=batch,
            machine_id=machine_id,
            operator_id=operator_id,
            base_time=base_time,
            prev_end=prev_end,
            machine_timeline=m_timeline,
            operator_timeline=operator_timeline.get(operator_id, []),
            end_dt_exclusive=end_dt_exclusive,
            machine_downtimes=m_downtimes,
            last_op_type_by_machine=last_op_type_by_machine,
            abort_after=abort_at,
            total_hours_base=total_hours_base,
            overlap_reuse=overlap_reuse,
        )

    estimate = None
    if handoff is not None:
        # The SGS witness cache keeps abort-free estimates per pair. An abort-free estimate starting after
        # abort_after is exactly the pair the native early stop would have pruned: the start only grows
        # across avoidance hops, so the native probe aborts iff its final start exceeds abort_after.
        estimate = handoff.pair_estimate(
            op=op, machine_id=machine_id, operator_id=operator_id, prev_end=prev_end,
            machine_timeline=machine_timeline, operator_timeline=operator_timeline, compute=lambda: estimate_pair(None),
        )
    if estimate is None:
        estimate = estimate_pair(abort_after)
    if estimate.abort_after_hit or (abort_after is not None and estimate.start_time > abort_after) or estimate.blocked_by_window:
        return None
    load_penalty = m_busy + operator_busy_hours.get(operator_id, 0.0)
    return (estimate.end_time, estimate.changeover_penalty, load_penalty, _pair_rank(pool, operator_id, machine_id), machine_id, operator_id)


def _pair_rank(pool: Dict[str, Any], operator_id: str, machine_id: str) -> int:
    return pool["pair_rank"].get((operator_id, machine_id), 9999)
