from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from core.algorithms import GreedyScheduler, ScheduleResult
from core.algorithms.evaluation import ScheduleMetrics, compute_metrics, objective_score
from core.algorithms.sort_strategies import SortStrategy
from core.algorithms.value_domains import INTERNAL
from core.infrastructure.errors import ValidationError
from core.models.schedule_config_runtime import default_snapshot_values
from core.services.scheduler.run.optimizer_proof_cases import TinyBenchmarkCase, TinyOperationSpec


@dataclass(frozen=True)
class ExactOracleResult:
    status: str
    best_score: Optional[Tuple[float, ...]]
    best_metrics: Optional[ScheduleMetrics]
    best_makespan_hours: Optional[float]
    nodes: int
    pruned_by_bound: int
    pruned_by_dominance: int
    runtime_ms: int


class _NodeLimitReached(Exception):
    pass


class _ContinuousCalendar:
    def adjust_to_working_time(self, dt: datetime, priority: Any = None, operator_id: Any = None) -> datetime:
        return dt

    def add_working_hours(self, dt: datetime, hours: float, priority: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(hours=float(hours or 0.0))

    def get_efficiency(self, dt: datetime, operator_id: Any = None) -> float:
        return 1.0

    def add_calendar_days(self, dt: datetime, days: float, machine_id: Any = None, operator_id: Any = None) -> datetime:
        return dt + timedelta(days=float(days or 0.0))


def run_exact_oracle(case: TinyBenchmarkCase, *, objective_name: str) -> ExactOracleResult:
    start = time.perf_counter()
    nodes = 0
    best_score: Optional[Tuple[float, ...]] = None
    best_metrics: Optional[ScheduleMetrics] = None
    best_makespan: Optional[float] = None
    try:
        for sequence in _iter_precedence_sequences(case):
            nodes += 1
            if nodes > int(case.oracle_node_limit):
                raise _NodeLimitReached()
            results = _decode_sequence(case, sequence)
            metrics = compute_metrics(results, batch_objects(case))
            score = (0.0,) + objective_score(objective_name, metrics)
            if best_score is None or score < best_score:
                best_score = score
                best_metrics = metrics
                best_makespan = float(metrics.makespan_hours)
    except _NodeLimitReached:
        return ExactOracleResult(
            status="node_limit",
            best_score=best_score,
            best_metrics=best_metrics,
            best_makespan_hours=best_makespan,
            nodes=nodes,
            pruned_by_bound=0,
            pruned_by_dominance=0,
            runtime_ms=_elapsed_ms(start),
        )
    return ExactOracleResult(
        status="proven_optimal",
        best_score=best_score,
        best_metrics=best_metrics,
        best_makespan_hours=best_makespan,
        nodes=nodes,
        pruned_by_bound=0,
        pruned_by_dominance=0,
        runtime_ms=_elapsed_ms(start),
    )


def run_case_with_greedy(case: TinyBenchmarkCase) -> Tuple[List[ScheduleResult], Any]:
    scheduler = GreedyScheduler(calendar_service=_ContinuousCalendar(), config_service=_default_config())
    results, summary, _strategy, _params = scheduler.schedule(
        operations=[_operation_object(op) for op in case.operations],
        batches=batch_objects(case),
        strategy=SortStrategy.PRIORITY_FIRST,
        start_dt=case.start_dt,
        dispatch_mode=case.dispatch_mode,
        dispatch_rule=case.dispatch_rule,
        seed_results=[],
        strict_mode=True,
    )
    return results, summary


def assert_oracle_decoder_matches_greedy(
    case: TinyBenchmarkCase,
    greedy_results: Sequence[ScheduleResult],
) -> None:
    """Fail-loud same-model guard for the tiny oracle proof.

    The exact oracle ranks sequences with the hand-rolled ``_decode_sequence``
    while the reported ``actual`` score comes from the production
    ``GreedyScheduler``. A ``proven_optimal`` / ``gap_to_oracle_pct == 0`` claim
    is only meaningful if both decoders measure on the *same* ruler. We do not
    trust that to hold by coincidence on degenerate cases: replay greedy's
    resulting schedule -- ordered by ``start_time`` (a valid topological order of
    that schedule, independent of greedy's dispatch order or any gap backfill) --
    through ``_decode_sequence`` and require an identical
    ``(start_time, end_time, machine_id, operator_id)`` per scheduled op. Under
    the tiny continuous model the waterline decoder reproduces any
    waterline-consistent schedule when fed in start-time order; any divergence
    means the two decoders are different models for this case, so the proof is
    not same-model and must fail loudly instead of publishing a gap measured with
    two rulers. Scope: this certifies greedy's *reported* schedule is same-model;
    it does not prove the oracle's whole enumeration is same-model -- that still
    requires the oracle to reuse greedy's decoder.
    """
    spec_by_op_id = {int(op.op_id): op for op in case.operations}
    scheduled = [
        result
        for result in greedy_results
        if result.start_time is not None and result.end_time is not None
    ]
    ordered = sorted(
        scheduled,
        key=lambda result: (result.start_time, result.end_time, int(result.op_id)),
    )
    try:
        sequence = tuple(spec_by_op_id[int(result.op_id)] for result in ordered)
    except KeyError as exc:
        raise ValidationError(
            "Greedy schedule references an operation absent from the tiny case.",
            field="oracle_decoder_parity",
            details={"case_slug": case.slug, "op_id": str(exc)},
        ) from exc
    decoded_by_op_id = {int(result.op_id): result for result in _decode_sequence(case, sequence)}
    for greedy_result in ordered:
        op_id = int(greedy_result.op_id)
        mirror = decoded_by_op_id.get(op_id)
        if mirror is None or not _schedule_slot_equal(greedy_result, mirror):
            raise ValidationError(
                "Exact-oracle decoder does not reproduce the GreedyScheduler schedule; "
                "the tiny oracle proof is not same-model for this case.",
                field="oracle_decoder_parity",
                details={
                    "case_slug": case.slug,
                    "op_id": op_id,
                    "greedy_slot": _slot_signature(greedy_result),
                    "oracle_slot": _slot_signature(mirror) if mirror is not None else None,
                },
            )


def _schedule_slot_equal(left: ScheduleResult, right: ScheduleResult) -> bool:
    return (
        left.start_time == right.start_time
        and left.end_time == right.end_time
        and str(left.machine_id or "") == str(right.machine_id or "")
        and str(left.operator_id or "") == str(right.operator_id or "")
    )


def _slot_signature(result: ScheduleResult) -> Dict[str, Any]:
    return {
        "start_time": result.start_time.isoformat() if result.start_time else None,
        "end_time": result.end_time.isoformat() if result.end_time else None,
        "machine_id": str(result.machine_id or ""),
        "operator_id": str(result.operator_id or ""),
    }


def batch_objects(case: TinyBenchmarkCase) -> Dict[str, Any]:
    return {
        batch.batch_id: SimpleNamespace(
            batch_id=str(batch.batch_id),
            priority=str(batch.priority),
            due_date=str(batch.due_date),
            ready_status="yes",
            ready_date=None,
            created_at=batch.created_at,
            quantity=float(batch.quantity),
        )
        for batch in case.batches
    }


def makespan_lower_bound(case: TinyBenchmarkCase) -> Tuple[float, Tuple[str, ...]]:
    batch_hours: Dict[str, float] = {}
    machine_hours: Dict[str, float] = {}
    operator_hours: Dict[str, float] = {}
    for op in case.operations:
        duration = float(op.duration_hours)
        batch_hours[op.batch_id] = batch_hours.get(op.batch_id, 0.0) + duration
        machine_hours[op.machine_id] = machine_hours.get(op.machine_id, 0.0) + duration
        operator_hours[op.operator_id] = operator_hours.get(op.operator_id, 0.0) + duration
    values = [
        max(batch_hours.values() or [0.0]),
        max(machine_hours.values() or [0.0]),
        max(operator_hours.values() or [0.0]),
    ]
    return float(max(values or [0.0])), ("critical_path", "machine_workload", "operator_workload")


def _iter_precedence_sequences(case: TinyBenchmarkCase) -> Iterable[Tuple[TinyOperationSpec, ...]]:
    ops_by_batch = _ops_by_batch(case)
    batch_ids = sorted(ops_by_batch.keys())
    next_idx = {batch_id: 0 for batch_id in batch_ids}
    total = sum(len(items) for items in ops_by_batch.values())

    def _walk(prefix: List[TinyOperationSpec]) -> Iterable[Tuple[TinyOperationSpec, ...]]:
        if len(prefix) == total:
            yield tuple(prefix)
            return
        for batch_id in batch_ids:
            idx = next_idx[batch_id]
            items = ops_by_batch[batch_id]
            if idx >= len(items):
                continue
            next_idx[batch_id] = idx + 1
            prefix.append(items[idx])
            yield from _walk(prefix)
            prefix.pop()
            next_idx[batch_id] = idx

    return _walk([])


def _decode_sequence(case: TinyBenchmarkCase, sequence: Sequence[TinyOperationSpec]) -> List[ScheduleResult]:
    machine_available: Dict[str, datetime] = {}
    operator_available: Dict[str, datetime] = {}
    batch_progress: Dict[str, datetime] = {}
    results: List[ScheduleResult] = []
    for op in sequence:
        earliest = max(
            case.start_dt,
            batch_progress.get(op.batch_id, case.start_dt),
            machine_available.get(op.machine_id, case.start_dt),
            operator_available.get(op.operator_id, case.start_dt),
        )
        end_time = earliest + timedelta(hours=float(op.duration_hours))
        results.append(
            ScheduleResult(
                op_id=int(op.op_id),
                op_code=str(op.op_code),
                batch_id=str(op.batch_id),
                seq=int(op.seq),
                machine_id=str(op.machine_id),
                operator_id=str(op.operator_id),
                start_time=earliest,
                end_time=end_time,
                source=INTERNAL,
                op_type_name=str(op.op_type_name or "") or None,
            )
        )
        machine_available[op.machine_id] = end_time
        operator_available[op.operator_id] = end_time
        batch_progress[op.batch_id] = end_time
    return results


def _operation_object(op: TinyOperationSpec) -> Any:
    return SimpleNamespace(
        id=int(op.op_id),
        op_code=str(op.op_code),
        batch_id=str(op.batch_id),
        seq=int(op.seq),
        source=INTERNAL,
        machine_id=str(op.machine_id),
        operator_id=str(op.operator_id),
        setup_hours=float(op.duration_hours),
        unit_hours=0.0,
        op_type_id="",
        op_type_name=str(op.op_type_name or ""),
    )


def _ops_by_batch(case: TinyBenchmarkCase) -> Dict[str, List[TinyOperationSpec]]:
    grouped: Dict[str, List[TinyOperationSpec]] = {}
    for op in case.operations:
        _validate_operation_spec(op)
        grouped.setdefault(str(op.batch_id), []).append(op)
    for batch in case.batches:
        grouped.setdefault(str(batch.batch_id), [])
    for batch_id, items in grouped.items():
        if not items:
            raise ValidationError(
                "Tiny benchmark batch has no operations.",
                field="operations",
                details={"case_slug": case.slug, "batch_id": batch_id},
            )
        items.sort(key=lambda item: (int(item.seq), int(item.op_id)))
    return grouped


def _validate_operation_spec(op: TinyOperationSpec) -> None:
    if int(op.op_id) <= 0:
        raise ValidationError("Tiny benchmark operation id must be positive.", field="op_id")
    if int(op.seq) <= 0:
        raise ValidationError("Tiny benchmark operation seq must be positive.", field="seq")
    if float(op.duration_hours) <= 0 or not math.isfinite(float(op.duration_hours)):
        raise ValidationError("Tiny benchmark duration must be a positive finite number.", field="duration_hours")
    if not str(op.machine_id or "").strip() or not str(op.operator_id or "").strip():
        raise ValidationError("Tiny benchmark operations must use fixed resources.", field="operation_resource")


def _default_config() -> Any:
    values = default_snapshot_values()
    values.update(
        {
            "sort_strategy": "priority_first",
            "dispatch_mode": "sgs",
            "dispatch_rule": "slack",
            "auto_assign_enabled": "no",
            "objective": "min_overdue",
            "algo_mode": "greedy",
            "time_budget_seconds": 1,
            "ortools_enabled": "no",
            "freeze_window_enabled": "no",
            "freeze_window_days": 0,
        }
    )
    return SimpleNamespace(**values)


def _elapsed_ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))
