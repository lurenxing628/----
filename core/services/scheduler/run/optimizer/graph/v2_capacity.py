from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Any, Dict, Iterable, List, Optional, Tuple

from core.algorithm_contracts.operator_eligibility import qualified_operators
from core.algorithm_contracts.value_domains import INTERNAL
from core.algorithms.greedy.seed import seed_resource_segments
from core.errors import ValidationError
from core.shared.strict_parse import finite_float, is_non_finite_number

_RESIDUAL_CAPACITY_MAX_WINDOW_DAYS = 30


class FixedResourceBlockingFacts:
    """Fixed blocking spans owned by one captured feature input, across its windows."""

    def __init__(self, *, downtime_map: Dict[str, List[Tuple[datetime, datetime]]],
                 seed_results_by_resource_id: Dict[str, Dict[str, List[Tuple[datetime, datetime]]]]) -> None:
        self._downtime_map = downtime_map
        self._seed_results = seed_results_by_resource_id
        self._downtime_segments: Dict[str, List[Tuple[datetime, datetime]]] = {}
        self._pairs: Dict[Tuple[str, Optional[str]], List[Tuple[datetime, datetime]]] = {}
        self._window_capacities: Dict[Tuple[str, Optional[str], Any, datetime, datetime], Tuple[float, float, float]] = {}
        self._calendar_windows: Dict[Tuple[Optional[str], Any, datetime, datetime], float] = {}
        self._pool_view: Optional[Tuple[Optional[Dict[str, Any]], _ResourcePoolView]] = None

    def pool_view(self, resource_pool: Optional[Dict[str, Any]]) -> _ResourcePoolView:
        if self._pool_view is None or self._pool_view[0] is not resource_pool:
            self._pool_view = (resource_pool, _ResourcePoolView(resource_pool))
        return self._pool_view[1]

    def _resource_seeds(self, kind: str, resource_id: Optional[str]) -> List[Tuple[datetime, datetime]]:
        # seed_results_by_resource_id always holds both kinds, keyed only by non-empty ids.
        return self._seed_results[kind].get(resource_id or "", [])

    def segments_for(self, machine_id: str, operator_id: Optional[str]) -> List[Tuple[datetime, datetime]]:
        key = machine_id, operator_id
        if key not in self._pairs:
            if machine_id not in self._downtime_segments:
                self._downtime_segments[machine_id] = _valid_segments(self._downtime_map.get(machine_id) or [])
            self._pairs[key] = _merge_segments(
                self._downtime_segments[machine_id]
                + self._resource_seeds("machine", machine_id)
                + self._resource_seeds("operator", operator_id)
            )
        return self._pairs[key]

    def window_capacity(
        self, key: Tuple[str, Optional[str], Any, datetime, datetime]
    ) -> Optional[Tuple[float, float, float]]:
        return self._window_capacities.get(key)

    def remember_window_capacity(
        self, key: Tuple[str, Optional[str], Any, datetime, datetime], value: Tuple[float, float, float]
    ) -> Tuple[float, float, float]:
        self._window_capacities[key] = value
        return value

    def calendar_window_hours(
        self,
        calendar_service: Any,
        start_dt: datetime,
        due_exclusive: datetime,
        *,
        priority: Any,
        operator_id: Optional[str],
    ) -> float:
        key = (operator_id, priority, start_dt, due_exclusive)
        if key not in self._calendar_windows:
            self._calendar_windows[key] = _calendar_capacity_hours(
                calendar_service,
                start_dt,
                due_exclusive,
                priority=priority,
                operator_id=operator_id,
            )
        return self._calendar_windows[key]


def residual_capacity_for_operation(
    op: Any,
    *,
    batch: Any,
    start_dt: datetime,
    due_exclusive: Optional[datetime],
    calendar_service: Any,
    resource_pool: Optional[Dict[str, Any]],
    prepared: FixedResourceBlockingFacts,
) -> Dict[str, float]:
    pool = prepared.pool_view(resource_pool)
    resource_key = (op.machine_id, op.operator_id, op.op_type_id)
    machine_ids = pool.candidate_machine_ids(op, key=resource_key)
    window_end = residual_capacity_window_end(start_dt=start_dt, due_exclusive=due_exclusive)
    if not machine_ids or window_end <= start_dt:
        return _capacity_payload(
            0.0,
            0.0,
            0.0,
            candidate_machine_count=0,
            resource_candidate_machine_count=len(machine_ids),
            bottleneck_machine_count=1 if machine_ids else 0,
        )

    priority = batch.priority if batch is not None else None
    machine_operators = pool.machine_operators(op, machine_ids=machine_ids, key=resource_key)
    effective_candidate_machine_count = len(machine_operators)
    candidates = [
        _machine_residual_capacity(
            machine_id=machine_id,
            operator_ids=operator_ids,
            start_dt=start_dt,
            due_exclusive=window_end,
            priority=priority,
            calendar_service=calendar_service,
            prepared=prepared,
        )
        for machine_id, operator_ids in machine_operators
    ]
    if not candidates:
        return _capacity_payload(
            0.0,
            0.0,
            0.0,
            candidate_machine_count=0,
            resource_candidate_machine_count=len(machine_ids),
            bottleneck_machine_count=1 if machine_ids else 0,
        )
    window_hours, blocked_hours, residual_hours = max(candidates, key=_capacity_rank)
    return _capacity_payload(
        window_hours,
        blocked_hours,
        residual_hours,
        candidate_machine_count=effective_candidate_machine_count,
        resource_candidate_machine_count=len(machine_ids),
        bottleneck_machine_count=effective_candidate_machine_count,
    )


def seed_results_by_resource_id(seed_results: Iterable[Any]) -> Dict[str, Dict[str, List[Tuple[datetime, datetime]]]]:
    out: Dict[str, Dict[str, List[Tuple[datetime, datetime]]]] = {"machine": {}, "operator": {}}
    for result in seed_results:
        if str(result.source or INTERNAL).strip().lower() != INTERNAL:
            continue
        segments = seed_resource_segments(result)
        if segments:
            for seg_start, seg_end, seg_machine_id, seg_operator_id in segments:
                if not (isinstance(seg_start, datetime) and isinstance(seg_end, datetime) and seg_end > seg_start):
                    continue
                span = (seg_start, seg_end)
                if seg_machine_id:
                    out["machine"].setdefault(seg_machine_id, []).append(span)
                if seg_operator_id:
                    out["operator"].setdefault(seg_operator_id, []).append(span)
            continue
        if not (
            isinstance(result.start_time, datetime)
            and isinstance(result.end_time, datetime)
            and result.end_time > result.start_time
        ):
            continue
        span = (result.start_time, result.end_time)
        if result.machine_id:
            out["machine"].setdefault(result.machine_id, []).append(span)
        if result.operator_id:
            out["operator"].setdefault(result.operator_id, []).append(span)
    return out


def residual_capacity_window_end(*, start_dt: datetime, due_exclusive: Optional[datetime]) -> datetime:
    max_end = start_dt + timedelta(days=_RESIDUAL_CAPACITY_MAX_WINDOW_DAYS)
    return max_end if due_exclusive is None else min(due_exclusive, max_end)


def bottleneck_on(*, bottleneck_score: float, residual_capacity_pressure: float, machine_count: int) -> float:
    if int(machine_count) <= 0:
        return float(bottleneck_score)
    residual_bonus = float(residual_capacity_pressure) / math.sqrt(float(machine_count))
    return float(bottleneck_score + residual_bonus)


def _machine_residual_capacity(
    *,
    machine_id: str,
    operator_ids: Tuple[str, ...],
    start_dt: datetime,
    due_exclusive: datetime,
    priority: Any,
    calendar_service: Any,
    prepared: FixedResourceBlockingFacts,
) -> Tuple[float, float, float]:
    operator_payloads = [
        _machine_operator_residual_capacity(
            machine_id=machine_id,
            operator_id=operator_id,
            start_dt=start_dt,
            due_exclusive=due_exclusive,
            priority=priority,
            calendar_service=calendar_service,
            prepared=prepared,
        )
        for operator_id in (operator_ids or (None,))
    ]
    return max(operator_payloads, key=_capacity_rank)


def _machine_operator_residual_capacity(
    *,
    machine_id: str,
    operator_id: Optional[str],
    start_dt: datetime,
    due_exclusive: datetime,
    priority: Any,
    calendar_service: Any,
    prepared: FixedResourceBlockingFacts,
) -> Tuple[float, float, float]:
    cache_key = (machine_id, operator_id, priority, start_dt, due_exclusive)
    cached = prepared.window_capacity(cache_key)
    if cached is not None:
        return cached
    window_hours = prepared.calendar_window_hours(
        calendar_service,
        start_dt,
        due_exclusive,
        priority=priority,
        operator_id=operator_id,
    )
    blocked_hours = _blocked_capacity_hours(
        calendar_service,
        start_dt,
        due_exclusive,
        prepared.segments_for(machine_id, operator_id),
        priority=priority,
        operator_id=operator_id,
        prepared=prepared,
    )
    residual_hours = max(0.0, float(window_hours) - float(blocked_hours))
    return prepared.remember_window_capacity(
        cache_key, (float(window_hours), float(blocked_hours), float(residual_hours))
    )


def _capacity_payload(
    window_hours: float,
    blocked_hours: float,
    residual_hours: float,
    *,
    candidate_machine_count: int,
    resource_candidate_machine_count: int,
    bottleneck_machine_count: int,
) -> Dict[str, float]:
    if window_hours <= 0.0:
        pressure = 1.0 if int(resource_candidate_machine_count) > 0 else 0.0
    else:
        ratio = max(0.0, min(1.0, float(residual_hours) / float(window_hours)))
        pressure = max(0.0, min(1.0, 1.0 - ratio))
    return {
        "residual_capacity_window_hours": float(window_hours),
        "residual_capacity_blocked_hours": float(blocked_hours),
        "residual_capacity_hours": float(residual_hours),
        "residual_capacity_pressure": float(pressure),
        "candidate_machine_count": int(candidate_machine_count),
        "bottleneck_machine_count": int(bottleneck_machine_count),
    }


def _capacity_rank(item: Tuple[float, float, float]) -> Tuple[float, float, float, float]:
    window_hours, blocked_hours, residual_hours = item
    ratio = float(residual_hours) / float(window_hours) if float(window_hours) > 0.0 else 0.0
    return (ratio, float(residual_hours), float(window_hours), -float(blocked_hours))


def _requires_auto_operator(op: Any, *, pool: _ResourcePoolView) -> bool:
    if op.operator_id:
        return False
    if op.machine_id:
        return True
    op_type_id = op.op_type_id
    return bool(op_type_id and op_type_id in pool.machines_by_op_type)


def _candidate_machine_ids(op: Any, *, pool: _ResourcePoolView) -> Tuple[str, ...]:
    fixed_machine = op.machine_id
    fixed_operator = op.operator_id
    op_type_id = op.op_type_id
    if fixed_machine:
        candidates = (fixed_machine,)
    elif fixed_operator:
        candidates = tuple(pool.machines_by_operator.get(fixed_operator, ()))
    elif op_type_id and op_type_id in pool.machines_by_op_type:
        return tuple(pool.machines_by_op_type[op_type_id])
    else:
        return ()
    if op_type_id and op_type_id in pool.machines_by_op_type:
        allowed = set(pool.machines_by_op_type[op_type_id])
        return tuple(machine_id for machine_id in candidates if machine_id in allowed)
    return candidates


def _candidate_operator_ids(op: Any, *, machine_id: str, pool: _ResourcePoolView) -> Tuple[str, ...]:
    return tuple(qualified_operators(
        pool.resource_pool, pool.operators_by_machine.get(machine_id, ()), op.op_type_id,
    ))


class _ResourcePoolView:
    def __init__(self, resource_pool: Optional[Dict[str, Any]]) -> None:
        self.resource_pool = resource_pool
        self.machines_by_op_type = {} if resource_pool is None else resource_pool["machines_by_op_type"]
        self.operators_by_machine = {} if resource_pool is None else resource_pool["operators_by_machine"]
        self.machines_by_operator = {} if resource_pool is None else resource_pool["machines_by_operator"]
        self._candidate_machines: Dict[Tuple[Optional[str], Optional[str], Optional[str]], Tuple[str, ...]] = {}
        self._machine_operators: Dict[
            Tuple[Optional[str], Optional[str], Optional[str]],
            Tuple[Tuple[str, Tuple[str, ...]], ...],
        ] = {}

    def candidate_machine_ids(
        self, op: Any, *, key: Tuple[Optional[str], Optional[str], Optional[str]]
    ) -> Tuple[str, ...]:
        if key not in self._candidate_machines:
            self._candidate_machines[key] = _candidate_machine_ids(op, pool=self)
        return self._candidate_machines[key]

    def machine_operators(
        self,
        op: Any,
        *,
        machine_ids: Tuple[str, ...],
        key: Tuple[Optional[str], Optional[str], Optional[str]],
    ) -> Tuple[Tuple[str, Tuple[str, ...]], ...]:
        if key not in self._machine_operators:
            requires_auto_operator = _requires_auto_operator(op, pool=self)
            fixed_operator = key[1]
            fixed_operator_ids = (
                tuple(qualified_operators(self.resource_pool, [fixed_operator], op.op_type_id))
                if fixed_operator
                else None
            )
            pairs: List[Tuple[str, Tuple[str, ...]]] = []
            for machine_id in machine_ids:
                operator_ids = (
                    fixed_operator_ids
                    if fixed_operator_ids is not None
                    else _candidate_operator_ids(op, machine_id=machine_id, pool=self)
                )
                if requires_auto_operator and not operator_ids:
                    continue
                pairs.append((machine_id, operator_ids))
            self._machine_operators[key] = tuple(pairs)
        return self._machine_operators[key]


def _valid_segments(segments: Iterable[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    return [
        (start, end)
        for start, end in segments
        if isinstance(start, datetime) and isinstance(end, datetime) and end > start
    ]


def _merge_segments(segments: Iterable[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Merge already valid positive spans from the fixed blocking preparation."""
    normalized = sorted(segments, key=lambda item: item[0])
    merged: List[Tuple[datetime, datetime]] = []
    for start, end in normalized:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        prev_start, prev_end = merged[-1]
        if end > prev_end:
            merged[-1] = (prev_start, end)
    return merged


def _blocked_capacity_hours(
    calendar_service: Any,
    start_dt: datetime,
    end_dt: datetime,
    segments: Iterable[Tuple[datetime, datetime]],
    *,
    priority: Any,
    operator_id: Optional[str],
    prepared: FixedResourceBlockingFacts,
) -> float:
    total = 0.0
    for block_start, block_end in segments:
        if block_start >= end_dt:
            break
        overlap_start = max(start_dt, block_start)
        overlap_end = min(end_dt, block_end)
        if overlap_end <= overlap_start:
            continue
        total += prepared.calendar_window_hours(
            calendar_service,
            overlap_start,
            overlap_end,
            priority=priority,
            operator_id=operator_id,
        )
    return float(total)


def _calendar_capacity_hours(
    calendar_service: Any,
    start_dt: datetime,
    end_dt: datetime,
    *,
    priority: Any,
    operator_id: Optional[str],
) -> float:
    if end_dt <= start_dt:
        return 0.0
    return non_negative_float(
        calendar_service.capacity_hours_between(start_dt, end_dt, priority=priority, operator_id=operator_id),
        field="calendar_capacity_hours",
    )


def non_negative_float(value: Any, *, field: str) -> float:
    """GraphReady v2 feature input: a finite, non-negative number (errors name the feature field)."""
    number = finite_float(value)
    if number is None:
        kind = "有限数字" if is_non_finite_number(value) else "数字"
        raise ValidationError(f"{field} 必须是{kind}。", field="graph_ready_v2_features")
    if number < 0.0:
        raise ValidationError(f"{field} 必须是非负数。", field="graph_ready_v2_features")
    return number


__all__ = [
    "FixedResourceBlockingFacts",
    "non_negative_float",
    "residual_capacity_window_end",
    "bottleneck_on",
    "residual_capacity_for_operation",
    "seed_results_by_resource_id",
]
