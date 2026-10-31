"""A bounded due-date priority seed, never a production schedule or an optimality certificate.

The caller restricts this to min_overdue. Moore/Hodgson's due-date queue motivates the first
order (Moore, 1968, https://pubsonline.informs.org/doi/10.1287/mnsc.15.1.102). Processing times
are observed result spans, with a common release offset; later calendars, individual releases
and resource changes are not modeled. Every proposed order still requires formal SGS validation.
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from datetime import datetime
from itertools import chain, combinations
from typing import Any, Callable, Dict, FrozenSet, Iterator, List, Optional, Tuple, cast

from core.algorithm_contracts.types import ScheduleResult
from core.algorithm_contracts.value_domains import INTERNAL

_MAX_PROBES = 2048


class _NotApplicable(ValueError):
    pass


class _ConstructionStopped(RuntimeError):
    pass


@dataclass(frozen=True)
class _Job:
    op_id: int
    processing: float
    due: float


class _Budget:
    def __init__(self, clock: Callable[[], float], deadline: float) -> None:
        self.clock, self.deadline = clock, deadline

    def check(self) -> None:
        if self.clock() >= self.deadline:
            raise _ConstructionStopped("time_budget")


def build_due_date_seed(*, parent: Any, candidate: Dict[str, Any], metrics: Dict[int, Dict[str, Any]],
                        graph_context: Dict[str, Any], start_dt: datetime,
                        clock: Callable[[], float], deadline: float) -> Optional[Tuple[int, ...]]:
    """Return a complete op-id tuple only when its estimated key strictly beats the original.

    probes counts distinct proposed orders induced by deferred sets; the original estimate is
    not a probe. A best completed probe can survive a later budget stop.
    """
    budget = _Budget(clock, deadline)
    search: Optional[_SeedSearch] = None
    try:
        budget.check()
        _check_graph(graph_context)
        order = parent.order
        jobs, offset = _observed_jobs(candidate, metrics, start_dt, budget)
        budget.check()
        search = _SeedSearch(jobs, offset, _estimate(order, jobs, offset), budget)
        deferred = _moore_deferred(search.jobs_by_due, offset, budget)
        key = search.probe(deferred)
        if len(deferred) <= 2 and math.comb(len(jobs), len(deferred)) <= _MAX_PROBES:
            for chosen in combinations(sorted(jobs), len(deferred)):
                search.probe(frozenset(chosen))
        else:
            _exchange_search(search, deferred, key)
            if len(deferred) > 2:
                _polish_order(search, search.best_order or order)
    except _NotApplicable:
        return None
    except _ConstructionStopped:
        pass
    return search.best_order if search is not None else None


def _check_graph(graph: Dict[str, Any]) -> None:
    if graph["fixed_op_ids"]:
        raise _NotApplicable("fixed_operations")
    # The graph links are validated bidirectional at decode preparation, and the parent's links are their
    # mutable slice, so the full predecessor map alone decides whether any precedence exists.
    if any(graph["predecessor_op_ids_by_op_id"].values()):
        raise _NotApplicable("precedence_constraints")


def _observed_jobs(candidate: Dict[str, Any], metrics: Dict[int, Dict[str, Any]],
                   start_dt: datetime, budget: _Budget) -> Tuple[Dict[int, _Job], float]:
    rows: List[ScheduleResult] = candidate["results"]
    jobs: Dict[int, _Job] = {}
    batches, resources, starts = set(), set(), []
    for row in rows:
        budget.check()
        op_id = row.op_id
        if row.batch_id in batches:
            raise _NotApplicable("not_one_operation_per_batch")
        batches.add(row.batch_id)
        resources.add(_resource_pair(row))
        processing = _observed_duration(row)
        starts.append(row.start_time)
        jobs[op_id] = _Job(op_id, processing, metrics[op_id]["due_deadline_hours"])
    if len(resources) != 1:
        raise _NotApplicable("multiple_resource_pairs")
    return jobs, _start_offset(starts, start_dt)


def _resource_pair(row: ScheduleResult) -> Tuple[Optional[str], Optional[str]]:
    if row.source != INTERNAL:
        raise _NotApplicable("non_internal_result")
    # A decoded internal row always names its machine and operator (internal_operation.py).
    return row.machine_id, row.operator_id


def _observed_duration(row: ScheduleResult) -> float:
    # Decoded rows carry the run's own datetimes with end >= start; zero-duration point events stay 0.
    return (cast(datetime, row.end_time) - cast(datetime, row.start_time)).total_seconds() / 3600.0


def _start_offset(starts: List[datetime], start_dt: datetime) -> float:
    return max((min(starts) - start_dt).total_seconds() / 3600.0, 0.0)


def _moore_deferred(jobs: Tuple[_Job, ...], offset: float, budget: _Budget) -> FrozenSet[int]:
    heap, deferred = [], set()
    completion = offset
    for job in jobs:
        budget.check()
        heapq.heappush(heap, (-job.processing, -job.due, -job.op_id))
        completion += job.processing
        # APS uses due_exclusive: finishing exactly at the deadline is already late.
        if completion >= job.due:
            negative_processing, _due, negative_op_id = heapq.heappop(heap)
            completion += negative_processing
            deferred.add(-negative_op_id)
    return frozenset(deferred)


def _order_for(deferred: FrozenSet[int], jobs_by_due: Tuple[_Job, ...],
               jobs_by_processing: Tuple[_Job, ...]) -> Tuple[int, ...]:
    early = (job.op_id for job in jobs_by_due if job.op_id not in deferred)
    late = (job.op_id for job in jobs_by_processing if job.op_id in deferred)
    return tuple(chain(early, late))


def _estimate(order: Tuple[int, ...], jobs: Dict[int, _Job], offset: float) -> Tuple[int, float]:
    completion, tardiness, late = offset, 0.0, 0
    for op_id in order:
        job = jobs[op_id]
        completion += job.processing
        late += int(completion >= job.due)
        tardiness += max(completion - job.due, 0.0)
    return late, tardiness


class _SeedSearch:
    def __init__(self, jobs: Dict[int, _Job], offset: float, original_key: Tuple[int, float], budget: _Budget) -> None:
        self.jobs, self.offset, self.budget = jobs, offset, budget
        self.jobs_by_due = tuple(sorted(jobs.values(), key=lambda job: (job.due, job.processing, job.op_id)))
        self.jobs_by_processing = tuple(sorted(jobs.values(), key=lambda job: (job.processing, job.due, job.op_id)))
        self.best_key = original_key
        self.best_order: Optional[Tuple[int, ...]] = None
        self.keys: Dict[FrozenSet[int], Tuple[int, float]] = {}
        self.orders: Dict[Tuple[int, ...], Tuple[int, float]] = {}
        self.probes = 0

    def probe(self, deferred: FrozenSet[int]) -> Tuple[int, float]:
        self.budget.check()
        if deferred in self.keys:
            return self.keys[deferred]
        order = _order_for(deferred, self.jobs_by_due, self.jobs_by_processing)
        key = self.probe_order(order)
        self.keys[deferred] = key
        return key

    def probe_order(self, order: Tuple[int, ...]) -> Tuple[int, float]:
        self.budget.check()
        if order in self.orders:
            return self.orders[order]
        if self.probes >= _MAX_PROBES:
            raise _ConstructionStopped("probe_limit")
        key = _estimate(order, self.jobs, self.offset)
        self.probes += 1
        self.orders[order] = key
        if key < self.best_key:
            self.best_key, self.best_order = key, order
        return key


def _single_exchanges(deferred: FrozenSet[int], jobs: Dict[int, _Job]) -> Iterator[FrozenSet[int]]:
    early = sorted(set(jobs).difference(deferred))
    for removed in sorted(deferred):
        for added in early:
            yield frozenset(deferred.difference((removed,)).union((added,)))


def _exchange_search(search: _SeedSearch, deferred: FrozenSet[int], key: Tuple[int, float]) -> None:
    while True:
        improved = _improving_exchange(search, deferred, key)
        if improved is None:
            return
        deferred, key = improved


def _improving_exchange(search: _SeedSearch, deferred: FrozenSet[int], key: Tuple[int, float]) -> Optional[Tuple[FrozenSet[int], Tuple[int, float]]]:
    for proposed in _single_exchanges(deferred, search.jobs):
        # All constructions share the same time guard and distinct-probe cap. A separate
        # 128-swap cutoff was abandoning cheap improvements for expensive SGS trials later.
        trial = search.probe(proposed)
        if trial < key:
            return proposed, trial
    return None


def _insertion_orders(order: Tuple[int, ...], jobs: Dict[int, _Job], offset: float) -> Iterator[Tuple[int, ...]]:
    completion, tardiness = offset, {}
    for op_id in order:
        completion += jobs[op_id].processing
        tardiness[op_id] = max(completion - jobs[op_id].due, 0.0)
    for op_id in sorted(order, key=lambda item: (-tardiness[item], item)):
        anchor = order.index(op_id)
        without = order[:anchor] + order[anchor + 1:]
        for position in sorted(range(len(order)), key=lambda item: (abs(item - anchor), item)):
            if position != anchor:
                yield without[:position] + (op_id,) + without[position:]


def _polish_order(search: _SeedSearch, order: Tuple[int, ...]) -> None:
    # Early-EDD / late-SPT alone cannot express a late job inserted into unused slack
    # between on-time jobs. Evaluate these orders cheaply before one formal SGS decode.
    # Every distinct order consumes the same global probe allowance and time guard.
    key = search.best_key
    while True:
        search.budget.check()
        for proposed in _insertion_orders(order, search.jobs, search.offset):
            trial = search.probe_order(proposed)
            if trial < key:
                order, key = proposed, trial
                break
        else:
            return


__all__ = ["build_due_date_seed"]
