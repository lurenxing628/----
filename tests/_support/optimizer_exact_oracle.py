"""Independent exact oracle for at most six non-preemptive single-resource ops.

This deliberately imports no production decoder, evaluator, or objective code.
The contract is the four vectors in core/models/objective.py; due minutes are
exclusive boundaries (completion exactly at the boundary counts as overdue).

All operations have release zero, fixed duration and the same fixed machine and
operator; calendars are continuous 24-hour availability, without downtime or
sequence-dependent setup. Every feasible schedule induces a topological order.
Left-packing that order cannot increase any completion time or changeover count,
and its span is the minimum possible sum of durations. Enumerating those orders
therefore proves the full lexicographic optimum *only in this restricted domain*.
Nonzero releases are rejected: earliest-order enumeration alone is insufficient
when delaying the first operation can reduce the production max-end/min-start
makespan. This is not a general APS optimality claim.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations
from typing import Dict, Tuple

OBJECTIVES = ("min_overdue", "min_tardiness", "min_weighted_tardiness", "min_changeover")
_METRIC_KEYS = {
    "min_overdue": ("overdue_count", "weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"),
    "min_tardiness": ("total_tardiness_hours", "overdue_count", "weighted_tardiness_hours", "makespan_hours", "changeover_count"),
    "min_weighted_tardiness": ("weighted_tardiness_hours", "total_tardiness_hours", "makespan_hours", "changeover_count"),
    "min_changeover": ("changeover_count", "overdue_count", "total_tardiness_hours", "weighted_tardiness_hours", "makespan_hours"),
}
_PRIORITY_WEIGHTS = {"normal": 1, "urgent": 2, "critical": 3}
SCOPE = "exact_within_single_fixed_resource_zero_release_continuous_calendar_domain"


@dataclass(frozen=True)
class TinyOperation:
    op_id: int
    batch_id: str
    duration_minutes: int
    predecessors: Tuple[int, ...] = ()
    release_minute: int = 0
    machine_id: str = "M0"
    operator_id: str = "O0"
    family: str = "TYPE0"


@dataclass(frozen=True)
class TinyCase:
    name: str
    operations: Tuple[TinyOperation, ...]
    due_minute_by_batch: Dict[str, int]
    priority_by_batch: Dict[str, str]


@dataclass(frozen=True)
class ScheduledOperation:
    op_id: int
    start_minute: int
    end_minute: int
    machine_id: str = "M0"
    operator_id: str = "O0"


@dataclass(frozen=True)
class ExactResult:
    best_score: Tuple[float, ...]
    schedules: Tuple[Tuple[ScheduledOperation, ...], ...]
    topological_orders: int
    applicability: str = SCOPE


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError(label + " must be an integer >= " + str(minimum))


def _text(value, label):
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError(label + " must be nonempty text without surrounding whitespace")


def _validate_case(case):
    _text(case.name, "case name")
    if not 1 <= len(case.operations) <= 6:
        raise ValueError("exact oracle accepts one to six operations")
    by_id = {}
    for op in case.operations:
        _integer(op.op_id, "operation id", 1)
        if op.op_id in by_id:
            raise ValueError("duplicate operation id")
        by_id[op.op_id] = op
        for label in ("batch_id", "machine_id", "operator_id", "family"):
            _text(getattr(op, label), label)
        _integer(op.duration_minutes, "duration", 1)
        _integer(op.release_minute, "release")
        if op.release_minute != 0:
            raise ValueError("exact domain requires zero release for every operation")
        for predecessor in op.predecessors:
            _integer(predecessor, "predecessor id", 1)
        if len(set(op.predecessors)) != len(op.predecessors):
            raise ValueError("duplicate predecessor")
    if len({(op.machine_id, op.operator_id) for op in case.operations}) != 1:
        raise ValueError("exact domain requires one fixed machine and operator pair")
    batches = {op.batch_id for op in case.operations}
    if set(case.due_minute_by_batch) != batches or set(case.priority_by_batch) != batches:
        raise ValueError("batch due dates and priorities must cover exactly the operation batches")
    for batch in batches:
        _integer(case.due_minute_by_batch[batch], "due boundary")
        if case.priority_by_batch[batch] not in _PRIORITY_WEIGHTS:
            raise ValueError("unknown priority")
    remaining, visited = set(by_id), set()
    for op in case.operations:
        if not set(op.predecessors).issubset(by_id):
            raise ValueError("unknown predecessor")
    while remaining:
        ready = {key for key in remaining if set(by_id[key].predecessors).issubset(visited)}
        if not ready:
            raise ValueError("cyclic precedence")
        remaining -= ready
        visited |= ready
    return by_id


def _validated_schedule(case, schedule):
    by_id = _validate_case(case)
    rows = tuple(schedule)
    ids = [row.op_id for row in rows]
    if len(ids) != len(by_id) or len(set(ids)) != len(ids) or set(ids) != set(by_id):
        raise ValueError("schedule must contain every operation exactly once")
    by_row_id = {row.op_id: row for row in rows}
    for row in rows:
        _integer(row.op_id, "scheduled operation id", 1)
        _integer(row.start_minute, "start minute")
        _integer(row.end_minute, "end minute")
        op = by_id[row.op_id]
        if (row.machine_id, row.operator_id) != (op.machine_id, op.operator_id):
            raise ValueError("schedule violates fixed resource eligibility")
        if row.end_minute - row.start_minute != op.duration_minutes:
            raise ValueError("schedule duration mismatch")
        if any(by_row_id[key].end_minute > row.start_minute for key in op.predecessors):
            raise ValueError("schedule violates precedence")
    ordered = sorted(rows, key=lambda row: (row.start_minute, row.end_minute, row.op_id))
    if any(left.end_minute > right.start_minute for left, right in zip(ordered, ordered[1:])):
        raise ValueError("schedule has a resource overlap")
    return by_id, ordered


def _score(case, by_id, ordered, objective):
    finish = {}
    for row in ordered:
        batch = by_id[row.op_id].batch_id
        finish[batch] = max(finish.get(batch, 0), row.end_minute)
    late = {batch: max(0, end - case.due_minute_by_batch[batch]) for batch, end in finish.items()}
    families = [by_id[row.op_id].family for row in ordered]
    metrics = {
        "overdue_count": sum(end >= case.due_minute_by_batch[batch] for batch, end in finish.items()),
        "total_tardiness_hours": sum(minutes / 60.0 for minutes in late.values()),
        "weighted_tardiness_hours": sum(minutes / 60.0 * _PRIORITY_WEIGHTS[case.priority_by_batch[batch]]
                                        for batch, minutes in late.items()),
        "makespan_hours": (ordered[-1].end_minute - ordered[0].start_minute) / 60.0,
        "changeover_count": sum(left != right for left, right in zip(families, families[1:])),
    }
    # Partial output is rejected, so failed_ops is always zero in this domain.
    return (0.0,) + tuple(float(metrics[key]) for key in _METRIC_KEYS[objective])


def score_schedule(case, schedule, objective):
    """Validate complete identity/precedence/resource/time data and score it."""
    if objective not in OBJECTIVES:
        raise ValueError("unknown objective")
    by_id, ordered = _validated_schedule(case, schedule)
    return _score(case, by_id, ordered, objective)


def solve_exact(case, objective):
    """Enumerate all topological orders and return all optimal packed schedules."""
    if objective not in OBJECTIVES:
        raise ValueError("unknown objective")
    by_id = _validate_case(case)
    best_score, winners, count = None, [], 0
    for order in permutations(by_id):
        seen, rows, clock = set(), [], 0
        for op_id in order:
            op = by_id[op_id]
            if not set(op.predecessors).issubset(seen):
                break
            rows.append(ScheduledOperation(op_id, clock, clock + op.duration_minutes, op.machine_id, op.operator_id))
            clock += op.duration_minutes
            seen.add(op_id)
        if len(rows) != len(by_id):
            continue
        count += 1
        score = _score(case, by_id, rows, objective)
        if best_score is None or score < best_score:
            best_score, winners = score, [tuple(rows)]
        elif score == best_score:
            winners.append(tuple(rows))
    return ExactResult(best_score, tuple(winners), count)


def compare_to_exact(case, schedule, objective):
    """Report a lexicographic gap, never a scalar/percentage quality claim."""
    candidate = score_schedule(case, schedule, objective)
    exact = solve_exact(case, objective)
    keys = ("failed_ops",) + _METRIC_KEYS[objective]
    gap = tuple(value - optimum for value, optimum in zip(candidate, exact.best_score))
    return {
        "score": candidate, "best_score": exact.best_score, "gap_vector": gap,
        "first_differing_metric": next((key for key, delta in zip(keys, gap) if delta != 0), None),
        "is_optimal": candidate == exact.best_score, "scope": exact.applicability,
        "explanation": "Compare vectors lexicographically; later negative deltas do not cancel an earlier positive gap. "
                       "Optimality covers this tiny fixed-resource zero-release case only.",
    }


def improving_case():
    """Input order A/B/C/D is strictly suboptimal under all four objectives."""
    return TinyCase(
        "tiny_exact_improving",
        (TinyOperation(1, "A", 1080, family="TYPE0"), TinyOperation(2, "B", 360, family="TYPE1"),
         TinyOperation(3, "C", 360, family="TYPE0"), TinyOperation(4, "D", 360, family="TYPE1")),
        {"A": 1440, "B": 1440, "C": 1440, "D": 2880},
        {"A": "normal", "B": "urgent", "C": "critical", "D": "normal"},
    )


def tie_chain_case():
    """One topological order; no strictly better schedule can exist."""
    return TinyCase(
        "tiny_exact_tie_chain",
        tuple(TinyOperation(index, "CHAIN", 360, predecessors=(index - 1,) if index > 1 else ())
              for index in range(1, 5)),
        {"CHAIN": 2880}, {"CHAIN": "normal"},
    )
