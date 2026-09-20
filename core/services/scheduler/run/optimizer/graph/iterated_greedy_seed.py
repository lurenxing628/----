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
from itertools import combinations
from typing import Any, Callable, Dict, FrozenSet, Iterator, Optional, Tuple

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


def _empty_result() -> Dict[str, Any]:
    return {"order": None, "status": "not_applicable", "reason": None, "estimated_key": None,
            "original_estimated_key": None, "probes": 0, "construction_stop": "not_applicable",
            "construction_method": None, "deferred_count": None, "estimated_start_offset_hours": None,
            "estimate_basis": "observed_result_spans_and_common_start_offset",
            "requires_sgs_validation": True, "optimality": "not_claimed"}


def build_due_date_seed(*, parent: Any, candidate: Dict[str, Any], metrics: Dict[int, Dict[str, Any]],
                        graph_context: Dict[str, Any], start_dt: datetime,
                        clock: Callable[[], float], deadline: float) -> Dict[str, Any]:
    """Return a complete op-id tuple only when its estimated key strictly beats the original.

    probes counts distinct proposed orders induced by deferred sets; the original estimate is
    not a probe. A best completed probe can survive a later budget stop, with that stop reported.
    """
    result, budget = _empty_result(), _Budget(clock, deadline)
    search: Optional[_SeedSearch] = None
    try:
        budget.check()
        order = _check_scope(parent, candidate, graph_context)
        jobs, offset = _observed_jobs(order, candidate, metrics, start_dt, budget)
        result["estimated_start_offset_hours"] = offset
        budget.check()
        search = _SeedSearch(jobs, offset, _estimate(order, jobs, offset), budget)
        deferred = _moore_deferred(jobs, offset, budget)
        result["deferred_count"] = len(deferred)
        key = search.probe(deferred)
        if len(deferred) <= 2 and math.comb(len(jobs), len(deferred)) <= _MAX_PROBES:
            result["construction_method"] = "enumerated_fixed_size_deferred_sets"
            for chosen in combinations(sorted(jobs), len(deferred)):
                search.probe(frozenset(chosen))
        else:
            result["construction_method"] = "bounded_single_exchange"
            _exchange_search(search, deferred, key)
            if len(deferred) > 2:
                result["construction_method"] = "bounded_single_exchange_and_insertion"
                _polish_order(search, search.best_order or order)
        result["construction_stop"] = "completed"
    except _NotApplicable as exc:
        result["reason"] = str(exc)
        if search is not None:
            result.update(probes=search.probes, original_estimated_key=search.original_key)
        return result
    except _ConstructionStopped as exc:
        result["construction_stop"] = str(exc)
    return _finish_result(result, search)


def _check_scope(parent: Any, candidate: Dict[str, Any], graph: Dict[str, Any]) -> Tuple[int, ...]:
    if parent is None or not isinstance(candidate, dict) or not isinstance(graph, dict):
        raise _NotApplicable("missing_parent_candidate_or_graph")
    order = tuple(parent.order)
    if not order or any(type(op_id) is not int for op_id in order) or len(set(order)) != len(order):
        raise _NotApplicable("invalid_parent_order")
    summary = candidate.get("summary")
    if not getattr(summary, "success", False) or getattr(summary, "failed_ops", None) != 0:
        raise _NotApplicable("candidate_not_successful")
    _check_graph(parent, graph)
    return order


def _check_graph(parent: Any, graph: Dict[str, Any]) -> None:
    if not isinstance(graph.get("fixed_op_ids"), (set, frozenset, list, tuple)):
        raise _NotApplicable("missing_fixed_operation_context")
    if graph["fixed_op_ids"]:
        raise _NotApplicable("fixed_operations")
    links = [parent.predecessors, parent.successors,
             graph.get("predecessor_op_ids_by_op_id"), graph.get("successor_op_ids_by_op_id")]
    if any(not isinstance(mapping, dict) for mapping in links):
        raise _NotApplicable("missing_precedence_context")
    edge_sets = [values for mapping in links for values in mapping.values()]
    if any(not isinstance(values, (set, frozenset, list, tuple)) for values in edge_sets):
        raise _NotApplicable("invalid_precedence_context")
    if any(edge_sets):
        raise _NotApplicable("precedence_constraints")


def _observed_jobs(order: Tuple[int, ...], candidate: Dict[str, Any], metrics: Dict[int, Dict[str, Any]],
                   start_dt: datetime, budget: _Budget) -> Tuple[Dict[int, _Job], float]:
    rows = candidate.get("results")
    if not isinstance(rows, (list, tuple)) or len(rows) != len(order):
        raise _NotApplicable("result_scope_mismatch")
    expected = set(order)
    jobs: Dict[int, _Job] = {}
    batches, resources, starts = set(), set(), []
    for row in rows:
        budget.check()
        op_id = getattr(row, "op_id", None)
        if type(op_id) is not int or op_id not in expected or op_id in jobs:
            raise _NotApplicable("result_scope_mismatch")
        batch = getattr(row, "batch_id", None)
        if not isinstance(batch, str) or not batch.strip() or batch in batches:
            raise _NotApplicable("not_one_operation_per_batch")
        batches.add(batch)
        resources.add(_resource_pair(row))
        processing = _observed_duration(row)
        starts.append(row.start_time)
        jobs[op_id] = _Job(op_id, processing, _due_deadline(metrics, op_id))
    if len(resources) != 1:
        raise _NotApplicable("multiple_resource_pairs")
    return jobs, _start_offset(starts, start_dt)


def _due_deadline(metrics: Any, op_id: int) -> float:
    metric = metrics.get(op_id) if isinstance(metrics, dict) else None
    due = metric.get("due_deadline_hours") if isinstance(metric, dict) else None
    if due is None or not _finite_number(due):
        raise _NotApplicable("missing_or_nonfinite_due_deadline_hours")
    return float(due)


def _resource_pair(row: Any) -> Tuple[str, str]:
    if getattr(row, "source", None) != "internal":
        raise _NotApplicable("non_internal_result")
    machine_id, operator_id = getattr(row, "machine_id", None), getattr(row, "operator_id", None)
    if (not isinstance(machine_id, str) or not machine_id.strip()
            or not isinstance(operator_id, str) or not operator_id.strip()):
        raise _NotApplicable("missing_resource_pair")
    return machine_id, operator_id


def _observed_duration(row: Any) -> float:
    start, end = getattr(row, "start_time", None), getattr(row, "end_time", None)
    if not isinstance(start, datetime) or not isinstance(end, datetime):
        raise _NotApplicable("invalid_result_times")
    try:
        hours = (end - start).total_seconds() / 3600.0
    except TypeError as exc:
        raise _NotApplicable("incompatible_result_timezones") from exc
    if not math.isfinite(hours) or hours < 0:
        raise _NotApplicable("invalid_observed_duration")
    return hours


def _start_offset(starts: Any, start_dt: datetime) -> float:
    if not isinstance(start_dt, datetime):
        raise _NotApplicable("invalid_start_dt")
    try:
        return max((min(starts) - start_dt).total_seconds() / 3600.0, 0.0)
    except TypeError as exc:
        raise _NotApplicable("incompatible_start_timezones") from exc


def _finite_number(value: Any) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _moore_deferred(jobs: Dict[int, _Job], offset: float, budget: _Budget) -> FrozenSet[int]:
    heap, deferred = [], set()
    completion = offset
    for job in sorted(jobs.values(), key=lambda item: (item.due, item.processing, item.op_id)):
        budget.check()
        heapq.heappush(heap, (-job.processing, -job.due, -job.op_id))
        completion += job.processing
        # APS uses due_exclusive: finishing exactly at the deadline is already late.
        if completion >= job.due:
            negative_processing, _due, negative_op_id = heapq.heappop(heap)
            completion += negative_processing
            deferred.add(-negative_op_id)
    return frozenset(deferred)


def _order_for(deferred: FrozenSet[int], jobs: Dict[int, _Job]) -> Tuple[int, ...]:
    early = sorted((job for job in jobs.values() if job.op_id not in deferred),
                   key=lambda job: (job.due, job.processing, job.op_id))
    late = sorted((jobs[op_id] for op_id in deferred), key=lambda job: (job.processing, job.due, job.op_id))
    return tuple(job.op_id for job in early + late)


def _estimate(order: Tuple[int, ...], jobs: Dict[int, _Job], offset: float) -> Tuple[int, float]:
    completion, tardiness, late = offset, 0.0, 0
    for op_id in order:
        job = jobs[op_id]
        completion += job.processing
        late += int(completion >= job.due)
        tardiness += max(completion - job.due, 0.0)
    if not math.isfinite(completion) or not math.isfinite(tardiness):
        raise _NotApplicable("nonfinite_estimate")
    return late, tardiness


class _SeedSearch:
    def __init__(self, jobs: Dict[int, _Job], offset: float, original_key: Tuple[int, float], budget: _Budget) -> None:
        self.jobs, self.offset, self.budget = jobs, offset, budget
        self.original_key = self.best_key = original_key
        self.best_order: Optional[Tuple[int, ...]] = None
        self.keys: Dict[FrozenSet[int], Tuple[int, float]] = {}
        self.orders: Dict[Tuple[int, ...], Tuple[int, float]] = {}
        self.probes = 0

    def probe(self, deferred: FrozenSet[int]) -> Tuple[int, float]:
        self.budget.check()
        if deferred in self.keys:
            return self.keys[deferred]
        order = _order_for(deferred, self.jobs)
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
    key = _estimate(order, search.jobs, search.offset)
    while True:
        search.budget.check()
        for proposed in _insertion_orders(order, search.jobs, search.offset):
            trial = search.probe_order(proposed)
            if trial < key:
                order, key = proposed, trial
                break
        else:
            return


def _finish_result(result: Dict[str, Any], search: Optional[_SeedSearch]) -> Dict[str, Any]:
    if search is not None:
        result.update(order=search.best_order, estimated_key=search.best_key,
                      original_estimated_key=search.original_key, probes=search.probes)
    if result["order"] is not None:
        result.update(status="candidate", reason="estimated_improvement")
    elif result["construction_stop"] != "completed":
        result.update(status="budget_exhausted", reason=result["construction_stop"])
    else:
        result.update(status="no_improvement", reason="estimate_not_better")
    return result


__all__ = ["build_due_date_seed"]
