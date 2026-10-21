from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Tuple

from core.algorithm_contracts.operator_eligibility import qualified_operators
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
)
from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithm_runtime.resource_quality import prefer_resource_pair
from core.algorithm_runtime.sgs_estimate_reuse import current_sgs_handoff
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse, overlap_reuse_for
from core.errors import ValidationError
from core.shared.strict_parse import parse_required_int


@dataclass(frozen=True)
class _MachineCandidates:
    values: List[str]
    reason: str = AUTO_ASSIGN_REASON_SUCCESS


@dataclass(frozen=True)
class ResourceCandidates:
    machines: Tuple[str, ...]
    fixed_operator: str
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


def prepare_resource_candidates(op: Any, resource_pool: Any) -> ResourceCandidates:
    fixed_machine, fixed_operator, op_type_id = _fixed_resource_inputs(op)
    pool, counters = _coerce_resource_pool(resource_pool), []
    if not fixed_machine and not op_type_id:
        return ResourceCandidates((), fixed_operator, op_type_id, pool, AUTO_ASSIGN_REASON_MISSING_OP_TYPE_ID,
                                  ("auto_assign_missing_op_type_id_count",))
    choice = _resolve_machine_candidates(fixed_machine=fixed_machine, fixed_operator=fixed_operator,
                                        op_type_id=op_type_id, pool=pool, count=counters.append)
    return ResourceCandidates(tuple(choice.values), fixed_operator, op_type_id, pool, choice.reason, tuple(counters))


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
    resource_preparation: Any = None,
    total_hours_by_op_id: Any = None,
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
        resource_preparation=resource_preparation,
        total_hours_by_op_id=total_hours_by_op_id,
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
    resource_preparation: Any = None,
    total_hours_by_op_id: Any = None,
) -> AutoAssignAttempt:
    calendar = calendar if calendar is not None else getattr(scheduler, "calendar", None)
    stats_target = algo_stats if algo_stats is not None else scheduler
    count = (lambda key: None) if probe_only else (lambda key: increment_counter(stats_target, key))
    candidates = (resource_preparation.resource_candidates_for(op) if resource_preparation is not None
                  else prepare_resource_candidates(op, resource_pool))
    for counter in candidates.counters:
        count(counter)
    if not candidates.machines:
        return AutoAssignAttempt(reason=candidates.reason)
    if resource_preparation is None:
        pool = candidates.pool
        pool["pair_rank"] = dict(pool["pair_rank"])
    elif resource_pool is resource_preparation.resource_pool:
        pool = candidates.pool
    else:
        pool = _coerce_resource_pool(resource_pool)
    total_hours_base = (total_hours_by_op_id.get(getattr(op, "id", None))
                        if total_hours_by_op_id is not None else None)
    if total_hours_base is None:
        total_hours_base = _validated_total_hours(op, batch, count=count)
    if total_hours_base is None:
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_INVALID_INTERNAL_HOURS)

    machine_candidates = _sort_machine_candidates(
        candidates.machines,
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
        fixed_operator=candidates.fixed_operator,
        machine_candidates=machine_candidates,
        total_hours_base=total_hours_base,
        last_op_type_by_machine=last_op_type_by_machine,
        machine_busy_hours=machine_busy_hours,
        operator_busy_hours=operator_busy_hours,
        count=count,
        static_candidates=candidates,
    )


def qualified_resource_pairs(op: Any, resource_pool: Any) -> Tuple[Tuple[str, str], ...]:
    """The shared machine, authorization and skill rule used by assignment and repair."""
    return prepare_resource_candidates(op, resource_pool).pairs


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
        **({"operator_skills": resource_pool["operator_skills"]} if "operator_skills" in resource_pool else {}),
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
    candidates: Iterable[str],
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
    static_candidates: Optional[ResourceCandidates] = None,
) -> AutoAssignAttempt:
    best: Optional[Tuple[Any, ...]] = None
    best_pair: Optional[Tuple[str, str]] = None
    seen_operator = False
    tie_seen = False
    window_blocked_pairs = 0
    non_window_infeasible_pairs = 0
    prev_end = batch_progress.get(str(getattr(op, "batch_id", "") or "").strip(), base_time)
    handoff = current_sgs_handoff()
    overlap_reuse = overlap_reuse_for(machine_timeline)
    for machine_id in machine_candidates:
        operator_candidates = (static_candidates.operators_for_machine(machine_id) if static_candidates is not None
                               else _operator_candidates_for_machine(machine_id, fixed_operator=fixed_operator, pool=pool,
                                                                     op_type_id=str(getattr(op, "op_type_id", "") or "")))
        if not operator_candidates:
            continue
        seen_operator = True
        m_timeline = machine_timeline.get(machine_id) or []
        m_downtimes = (machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else []
        m_busy = float(machine_busy_hours.get(machine_id, 0.0) or 0.0)
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
                handoff=handoff,
                m_timeline=m_timeline,
                m_downtimes=m_downtimes,
                m_busy=m_busy,
                overlap_reuse=overlap_reuse,
            )
            if probe.score is not None:
                if best is not None and probe.score[:2] == best[:2]:
                    tie_seen = True
                if best is None or prefer_resource_pair(last_op_type_by_machine, op, probe.score, best):
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
    return AutoAssignAttempt(machine_id=best_pair[0], operator_id=best_pair[1], pair_tie_occurred=tie_seen)


def _pair_failure_attempt(
    *,
    seen_operator: bool,
    window_blocked_pairs: int,
    non_window_infeasible_pairs: int,
    count: Any,
) -> AutoAssignAttempt:
    if not seen_operator:
        count("auto_assign_no_operator_candidate_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_NO_OPERATOR_CANDIDATE, pair_tie_occurred=False)
    # 窗口归因规则：仅当"所有被评估的机-人组合都因排产截止窗口被拒、且不存在窗口外原因的
    # 不可行判定"时才归因 WINDOW_BLOCKED；混合场景（存在窗口外原因的不可行判定）保持
    # NO_FEASIBLE_PAIR，宁可保守也不把非窗口问题伪装成截止日期问题。
    # 注：abort_after 剪枝（非窗口 None）只会在已找到可行 best 后出现，走不到这里，
    # 这里对它的计数纯属防御。
    if window_blocked_pairs > 0 and non_window_infeasible_pairs == 0:
        count("auto_assign_window_blocked_count")
        return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_WINDOW_BLOCKED, pair_tie_occurred=False)
    count("auto_assign_no_feasible_pair_count")
    return AutoAssignAttempt(reason=AUTO_ASSIGN_REASON_NO_FEASIBLE_PAIR, pair_tie_occurred=False)


def _operator_candidates_for_machine(machine_id: str, *, fixed_operator: str, pool: Dict[str, Any], op_type_id="") -> List[str]:
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
    handoff: Any = None,
    m_timeline: Optional[List[Tuple[datetime, datetime]]] = None,
    m_downtimes: Optional[List[Tuple[datetime, datetime]]] = None,
    m_busy: Optional[float] = None,
    overlap_reuse: Optional[SlotOverlapReuse] = None,
) -> _PairProbe:
    if m_timeline is None:
        m_timeline = machine_timeline.get(machine_id) or []
        if overlap_reuse is None:
            overlap_reuse = overlap_reuse_for(machine_timeline)
    if m_downtimes is None:
        m_downtimes = (machine_downtimes.get(machine_id) or []) if machine_downtimes and machine_id else []
    if m_busy is None:
        m_busy = float(machine_busy_hours.get(machine_id, 0.0) or 0.0)

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
            operator_timeline=operator_timeline.get(operator_id) or [],
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
    if estimate.abort_after_hit or (abort_after is not None and estimate.start_time > abort_after):
        return _PairProbe(score=None, window_blocked=False)
    if estimate.blocked_by_window:
        return _PairProbe(score=None, window_blocked=True)
    load_penalty = m_busy + float(operator_busy_hours.get(operator_id, 0.0) or 0.0)
    return _PairProbe(
        score=(estimate.end_time, int(estimate.changeover_penalty), float(load_penalty), _pair_rank(pool, operator_id, machine_id), machine_id, operator_id),
        window_blocked=False,
    )


def _pair_rank(pool: Dict[str, Any], operator_id: str, machine_id: str) -> int:
    pair = (operator_id, machine_id)
    if pair not in pool["pair_rank"]:
        return 9999
    try:
        value = pool["pair_rank"][pair]
        if type(value) is int:
            return value
        normalized = parse_required_int(value, field="pair_rank")
        pool["pair_rank"][pair] = normalized
        return normalized
    except ValidationError as exc:
        raise ValidationError(f"pair_rank 必须是整数：operator_id={operator_id!r} machine_id={machine_id!r}", field="pair_rank") from exc


_NATIVE_AUTO_ASSIGN = {name: globals()[name] for name in (
    "auto_assign_internal_resources_attempt", "_resolve_machine_candidates", "_sort_machine_candidates",
    "_choose_best_pair", "_pair_score", "_pair_rank", "_operator_candidates_for_machine", "_sort_operator_candidates",
    "estimate_internal_slot", "prefer_resource_pair", "validate_internal_hours",
)}


def native_auto_assign_unchanged() -> bool:
    """The probe still runs the module's own code; a monkeypatched helper must be observed on every call."""
    return all(globals()[name] is original for name, original in _NATIVE_AUTO_ASSIGN.items())
