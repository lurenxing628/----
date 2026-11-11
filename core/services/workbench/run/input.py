"""Prepare strictly scoped business input; solver resources are prepared separately."""

from __future__ import annotations

import time
from dataclasses import dataclass, replace
from datetime import date, datetime
from typing import TYPE_CHECKING, AbstractSet, Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from core.algorithm_contracts.operation_effort import OperationEffort
from core.algorithm_contracts.types import OpForScheduleAlgo
from core.models.batch import Batch
from core.models.batch_operation import BatchOperation
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_preflight import local_date, normalize_preflight_input
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_input_contracts import (
    ExecutionGuardState,
    SeedPreparation,
    SolverInput,
)
from core.services.scheduler.run.schedule_input_seed_metadata import merged_actual_group_intervals
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.run_input_rows import (
    admitted_classification,
    batch_model,
    classify_rows,
    fail,
    operation_model,
    preflight_classification,
    validate_single_chain,
)

from .input_config import candidate_config, hold_window
from .input_effort import prepare_operation_efforts
from .input_execution import execution_guards
from .input_external import execution_groups, external_execution_cycles, verified_external_contexts
from .input_piece import input_piece_scope
from .input_runtime import prepare_seed_preparation

if TYPE_CHECKING:
    from core.models.workbench_piece_adoption import PieceAdoptionScope

    from .preflight_facts import PreflightFacts

_CLASSIFY_CURRENT = object()


@dataclass(frozen=True)
class PreparedBusinessInput:
    settings: Mapping[str, Any]
    facts: PreflightFacts
    normalized_batch_ids: List[str]
    batches: Dict[str, Batch]
    operations: List[BatchOperation]
    algo_ops: List[OpForScheduleAlgo]
    config: ScheduleConfigSnapshot
    start: datetime
    end_date: date
    readiness_gate_enabled: bool
    execution_guard: ExecutionGuardState
    seeds: SeedPreparation
    piece_scope: Optional[PieceAdoptionScope]
    predecessors: Mapping[int, Sequence[int]]
    dispositions: List[Dict[str, Any]]
    baseline_version: int
    latest_plan_rows: Mapping[int, Mapping[str, Any]]
    allowed_op_ids: Set[int]
    missing_internal_resource_op_ids: Set[int]
    operation_sources: Dict[int, str]
    operation_efforts: Sequence[OperationEffort]
    t0: float


def prepare_solver_input(business: PreparedBusinessInput) -> SolverInput:
    return SolverInput(
        batches=business.batches,
        algo_ops=business.algo_ops,
        to_schedule=business.seeds.to_schedule,
        config=business.config,
        start=business.start,
        end_date=business.end_date,
        readiness_gate_enabled=business.readiness_gate_enabled,
        seeds=business.seeds,
        predecessors=business.predecessors,
    )


def prepare_business_input(
    conn,
    normalized_input: Mapping[str, Any],
    execution_projections: Sequence[ExecutionProjection],
    *,
    facts: PreflightFacts,
    config_snapshot: Optional[ScheduleConfigSnapshot] = None,
    baseline: Optional[Mapping[str, Any]] = None,
    held: Any = None,
    preflight_rows: Optional[Sequence[Mapping[str, Any]]] = None,
    admitted_dispositions: Any = _CLASSIFY_CURRENT,
    admitted_piece_scope: Optional[PieceAdoptionScope] = None,
    include_efforts: bool = True,
) -> PreparedBusinessInput:
    """Read-only business preparation. Caller supplies selected + last-official execution scope."""
    settings = normalized_input if preflight_rows is not None else normalize_preflight_input(normalized_input)
    if not settings["batch_refs"]:
        fail("empty_scope", "请先勾选要排产的批次。")
    with candidate_read_snapshot(conn):
        raw_batches, batches, operations, piece_scope, predecessors, base_config, cfg, prev_version = (
            _prepare_scope_and_config(facts, settings, config_snapshot, baseline, admitted_piece_scope)
        )
        projections = {proj.operation_ref: proj for proj in execution_projections}
        start = datetime.combine(local_date(settings["start_date"]), datetime.min.time())
        guard, dispositions, mutable, guarded_ids, algo_ops, seeds = _prepare_execution_and_seeds(
            conn, facts=facts, settings=settings, raw_batches=raw_batches, batches=batches,
            operations=operations, projections=projections, prev_version=prev_version, start=start,
            base_config=base_config, piece_scope=piece_scope, held=held, preflight_rows=preflight_rows,
            admitted_dispositions=admitted_dispositions,
        )
        efforts = (
            prepare_operation_efforts(
                conn, facts=facts, operations=operations, batches=batches, algo_ops=algo_ops,
                seeds=seeds, execution_facts=guard.execution_facts, projections=projections,
            )
            if include_efforts
            else ()
        )
        return PreparedBusinessInput(
            settings=settings, facts=facts,
            normalized_batch_ids=[row["batch_id"] for row in raw_batches],
            batches=batches, operations=operations, algo_ops=algo_ops, config=cfg, start=start,
            end_date=local_date(settings["end_date"]),
            readiness_gate_enabled=settings["ready_check"],
            execution_guard=guard, seeds=seeds, piece_scope=piece_scope, predecessors=predecessors,
            dispositions=dispositions, baseline_version=prev_version,
            latest_plan_rows=facts.latest_plan_rows(prev_version),
            allowed_op_ids={op.id for op in mutable} | guarded_ids,
            missing_internal_resource_op_ids=_missing_internal_resources(mutable),
            operation_sources={op.id: op.source for op in operations},
            operation_efforts=efforts, t0=time.monotonic(),
        )


def _prepare_scope_and_config(
    facts: PreflightFacts,
    settings: Mapping[str, Any],
    config_snapshot: Optional[ScheduleConfigSnapshot],
    baseline: Optional[Mapping[str, Any]],
    admitted_piece_scope: Optional[PieceAdoptionScope],
):
    raw_batches = facts.selected(settings["batch_refs"])
    batches = {row["batch_id"]: batch_model(row) for row in raw_batches}
    operations = [operation_model(row) for row in facts.tables["BatchOperations"] if row["batch_id"] in batches]
    piece_scope = (
        admitted_piece_scope if admitted_piece_scope is not None else input_piece_scope(operations, batches)
    )
    if piece_scope is None:
        validate_single_chain(operations)
    predecessors = (
        {work.op_id: tuple(work.predecessor_op_ids) for work in piece_scope.operations}
        if piece_scope is not None
        else {}
    )
    base_config = facts.configuration() if config_snapshot is None else config_snapshot
    cfg = candidate_config(settings, snapshot=base_config)
    if piece_scope is not None:
        cfg = replace(cfg, dispatch_mode="sgs")
    prev_version = (
        max((row["version"] for row in facts.capture.table("ScheduleHistory")), default=0)
        if baseline is None
        else baseline["version"] or 0
    )
    return raw_batches, batches, operations, piece_scope, predecessors, base_config, cfg, prev_version


def _prepare_execution_and_seeds(
    conn,
    *,
    facts: PreflightFacts,
    settings: Mapping[str, Any],
    raw_batches: Sequence[Mapping[str, Any]],
    batches: Dict[str, Batch],
    operations: List[BatchOperation],
    projections: Mapping[str, ExecutionProjection],
    prev_version: int,
    start: datetime,
    base_config: Optional[ScheduleConfigSnapshot],
    piece_scope: Optional[PieceAdoptionScope],
    held: Any,
    preflight_rows: Optional[Sequence[Mapping[str, Any]]],
    admitted_dispositions: Any,
) -> Tuple[ExecutionGuardState, List[Dict[str, Any]], List[BatchOperation], Set[int], List[OpForScheduleAlgo], SeedPreparation]:
    execution_guard = execution_guards(
        facts, operations, batches, projections, prev_version, piece_scope=piece_scope
    )
    completed = execution_guard.execution_completed_op_ids
    execution_seeds = execution_guard.execution_seed_results
    actual_group_intervals = merged_actual_group_intervals(
        execution_groups(facts, batches, operations),
        execution_seeds,
    )
    cycles = (
        {
            row["op_id"]: dict(row["external_execution_cycle"])
            for row in preflight_rows
            if "external_execution_cycle" in row and row["op_id"] not in completed
        }
        if preflight_rows is not None
        else external_execution_cycles(facts, batches, operations, actual_group_intervals, completed)
    )
    guarded_ids = set(completed) | set(cycles)
    dispositions, mutable, releases = _resolve_dispositions(
        facts,
        settings,
        raw_batches,
        operations,
        projections,
        completed,
        guarded_ids,
        cycles,
        piece_scope=piece_scope,
        preflight_rows=preflight_rows,
        admitted_dispositions=admitted_dispositions,
    )
    algo_ops, runtime_mutable = _algorithm_scope(
        facts, batches, operations, mutable, guarded_ids, cycles, releases
    )
    seeds = prepare_seed_preparation(
        conn,
        facts=facts,
        prev_version=prev_version,
        start_dt=start,
        operations=operations,
        mutable=runtime_mutable,
        algo_ops=algo_ops,
        completed_ids=completed,
        execution_seeds=execution_seeds,
        actual_group_intervals=actual_group_intervals,
        hold_window=hold_window(settings, snapshot=base_config)[0] if held is None else None,
        piece_scope=piece_scope,
        held=held,
    )
    return execution_guard, dispositions, mutable, guarded_ids, algo_ops, seeds


def _resolve_dispositions(
    facts: PreflightFacts,
    settings: Mapping[str, Any],
    raw_batches: Sequence[Mapping[str, Any]],
    operations: List[BatchOperation],
    projections: Mapping[str, ExecutionProjection],
    completed: AbstractSet[int],
    guarded_ids: Set[int],
    cycles: Mapping[int, Dict[str, Any]],
    *,
    piece_scope: Optional[PieceAdoptionScope],
    preflight_rows: Optional[Sequence[Mapping[str, Any]]],
    admitted_dispositions: Any,
):
    if admitted_dispositions is not _CLASSIFY_CURRENT:
        return admitted_classification(operations, admitted_dispositions, guarded_ids)
    if preflight_rows is not None:
        return preflight_classification(
            operations,
            projections,
            completed,
            preflight_rows,
            external_cycles=cycles,
        )
    return classify_rows(
        facts,
        settings,
        raw_batches,
        operations,
        projections,
        completed,
        piece_scope=piece_scope,
        external_cycles=cycles,
    )


def _algorithm_scope(facts, batches, operations, mutable, guarded_ids, cycles, releases):
    guarded = [op for op in operations if op.id in guarded_ids]
    external_contexts = verified_external_contexts(facts.tables, batches, mutable + guarded)
    algo_ops = build_algo_operations(mutable + guarded, external_contexts=external_contexts)
    for op in algo_ops:
        if op.id not in guarded_ids:
            # Release days are canonical ISO dates (stage_availability.arrival_day); parse them once here.
            release = releases[op.id]
            op.material_ready_date = None if release is None else datetime.fromisoformat(release)
    # Derived peers are fixed for calculation, but must still take part in the
    # original lock/freeze lookup so their inherited locks cannot be overwritten.
    runtime_mutable = mutable + [op for op in guarded if op.id in cycles]
    return algo_ops, runtime_mutable


def _missing_internal_resources(operations):
    return {op.id for op in operations if op.source == "internal" and (op.machine_id is None or op.operator_id is None)}


__all__ = [
    "PreparedBusinessInput",
    "prepare_business_input",
    "prepare_solver_input",
]
