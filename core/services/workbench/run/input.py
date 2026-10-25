"""Prepare strictly scoped candidate input; never call the legacy run collector."""

import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, List, Sequence

from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_preflight import local_date, normalize_preflight_input
from core.services.scheduler.repository_bundle import build_schedule_repository_bundle
from core.services.scheduler.run.operation_effort import build_operation_efforts
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    build_execution_resource_reservations,
)
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_input_contracts import ScheduleRunInput
from core.services.workbench.facts.run_input_codec import validate_projection_dto
from core.services.workbench.facts.run_input_readonly import candidate_read_snapshot
from core.services.workbench.facts.run_input_rows import (
    batch_model,
    classify_rows,
    fail,
    operation_model,
    validate_single_chain,
)

from .input_config import candidate_config, hold_window
from .input_effort import saved_seed_efforts
from .input_execution import execution_guards
from .input_external import external_execution_cycles, verified_external_contexts
from .input_piece import input_piece_scope
from .input_runtime import build_runtime
from .preflight_facts import PreflightFacts


@dataclass
class CandidateRunInput(ScheduleRunInput):
    normalized_input: Dict[str, Any] = field(default_factory=dict)
    dispositions: List[Dict[str, Any]] = field(default_factory=list)
    preflight_facts: Any = None
    execution_reservations: List[Any] = field(default_factory=list)
    latest_plan_rows: Dict[int, Any] = field(default_factory=dict)
    piece_scope: Any = None


def _projection_map(execution_projections, selected_refs, *, validated):
    if not isinstance(execution_projections, (list, tuple)):
        fail("execution_projection_type", "Supply AJ ExecutionProjection objects, not a reconstructed dictionary.")
    result = {}
    for projection in execution_projections:
        if not isinstance(projection, ExecutionProjection):
            fail("execution_projection_type", "Every execution item must be an AJ ExecutionProjection.")
        if validated is None or validated.get(projection.operation_ref) is not projection:
            validate_projection_dto(projection)
        if projection.operation_ref in result:
            fail("execution_projection_duplicate", "同一道工序读到了多份报工记录，这次排产没有开始。请刷新重试；仍不行请联系维护人员。")
        result[projection.operation_ref] = projection
    if not set(selected_refs) <= set(result):
        fail("execution_projection_missing", "有选中的工序读不到报工记录，这次排产没有开始。请重新做排产检查后再排。")
    return result


def prepare_candidate_run_input(conn, normalized_input: Dict[str, Any],
                                execution_projections: Sequence[ExecutionProjection], *,
                                facts=None, config_snapshot=None, baseline=None, validated_projections=None,
                                for_adoption: bool = False, held=None) -> CandidateRunInput:
    """Read-only. Caller supplies AJ selected + all last-official execution scope.

    The worker owns the existing run lock and its admission/final revalidation.
    This function neither acquires that lock nor accepts/publishes a run.
    Adoption keeps input and seed validation but does not prepare solver resources.
    """
    settings = normalize_preflight_input(normalized_input)
    if not settings["batch_refs"]:
        fail("empty_scope", "请先勾选要排产的批次。")
    with candidate_read_snapshot(conn):
        if facts is not None:
            if facts.conn is not conn or not conn.in_transaction:
                raise RuntimeError("Prepared input requires this transaction's own production facts")
            with facts.execution_snapshot():
                return _prepare_facts(conn, settings, facts, execution_projections,
                                      config_snapshot, baseline, validated_projections, for_adoption=for_adoption,
                                      held=held)
        facts = PreflightFacts(conn)
        with facts.snapshot(fingerprint=False):
            return _prepare_facts(conn, settings, facts, execution_projections,
                                  config_snapshot, baseline, validated_projections, for_adoption=for_adoption,
                                  held=held)


def _prepare_facts(conn, settings, facts, execution_projections,
                   config_snapshot, baseline, validated_projections, *, for_adoption: bool, held):
    raw_batches = facts.selected(settings["batch_refs"])
    batches = {row["batch_id"]: batch_model(row) for row in raw_batches}
    raw_ops = [row for row in facts.tables["BatchOperations"] if row["batch_id"] in batches]
    operations = [operation_model(row) for row in raw_ops]
    projections = _projection_map(execution_projections, [facts.operation_ref(row) for row in raw_ops],
                                  validated=validated_projections)
    facts.execution_projections.update(projections)
    return _prepare(conn, settings, facts, raw_batches, batches, operations, projections,
                    config_snapshot=config_snapshot, baseline=baseline, for_adoption=for_adoption, held=held)


def _prepare(conn, settings, facts, raw_batches, batches, operations, projections, *,
             config_snapshot, baseline, for_adoption: bool, held):
    piece_scope = input_piece_scope(operations, batches)
    if piece_scope is None:
        validate_single_chain(operations)
    svc = build_schedule_repository_bundle(conn)
    base_config = facts.configuration() if config_snapshot is None else config_snapshot
    cfg = candidate_config(settings, snapshot=base_config)
    if piece_scope is not None:
        cfg = replace(cfg, dispatch_mode="sgs")
    prev_version = (max((row["version"] for row in facts.capture.table("ScheduleHistory")), default=0)
                    if baseline is None else baseline["version"] or 0)
    start = datetime.combine(local_date(settings["start_date"]), datetime.min.time())
    guards = execution_guards(svc, facts, operations, batches, projections, prev_version, piece_scope=piece_scope)
    execution_facts, fixed, completed, execution_seeds, snapshot = guards
    cycles = external_execution_cycles(facts, batches, operations, execution_seeds, set(fixed) | set(completed))
    dispositions, mutable, releases = classify_rows(
        facts, settings, raw_batches, operations, projections,
        set(fixed) | set(completed), piece_scope=piece_scope, external_cycles=cycles,
    )
    guarded_ids = set(fixed) | set(completed) | set(cycles)
    algo_ops, runtime_mutable = _algorithm_scope(facts, batches, operations, mutable, guarded_ids, cycles, releases)
    reservations = build_execution_resource_reservations(
        facts=execution_facts, selected_op_ids={op.id for op in operations}, start_dt=start, capture=facts.capture,
    )
    calendar = facts.calendar()
    if reservations:
        calendar = ExecutionResourceCalendar(calendar, reservations)
    runtime = build_runtime(
        svc, cfg=cfg, prev_version=prev_version, start_dt=start, batches=batches, operations=operations,
        mutable=runtime_mutable, algo_ops=algo_ops, fixed_ids=fixed, completed_ids=completed,
        execution_seeds=execution_seeds, reservations=reservations,
        hold_window=hold_window(settings, snapshot=base_config)[0] if held is None else None,
        facts=facts, piece_scope=piece_scope,
        for_adoption=for_adoption, held=held,
    )
    frozen, seeds, freeze_meta, to_schedule, downtime_meta, pool_meta, downtime, pool, seed_version = runtime
    missing_ids = _missing_internal_resources(mutable)
    efforts = [] if for_adoption else build_operation_efforts(
        operations=operations, batches=batches, algo_operations=algo_ops, operations_to_schedule=to_schedule,
        seed_results=seeds, execution_facts=execution_facts,
        execution_projections={op.id: projections[facts.operation_refs[op.id]] for op in operations},
        saved_efforts=saved_seed_efforts(svc, facts, seeds, execution_facts),
    )
    return CandidateRunInput(
        normalized_batch_ids=[row["batch_id"] for row in raw_batches], start_dt_norm=start,
        end_date_norm=local_date(settings["end_date"]),
        t0=time.time(), cal_svc=calendar, cfg_svc=None, cfg=cfg, readiness_gate_enabled=settings["ready_check"],
        batches=batches, operations=operations, missing_internal_resource_op_ids=missing_ids,
        algo_ops=algo_ops, prev_version=prev_version,
        frozen_op_ids=frozen, seed_results=seeds, execution_facts=execution_facts,
        execution_fixed_op_ids=fixed, execution_completed_op_ids=completed, execution_seed_results=execution_seeds,
        execution_snapshot_revision=snapshot.revision,
        execution_snapshot_op_ids=list(snapshot.op_ids), execution_snapshot_op_count=snapshot.op_count,
        schedule_output_allowed_op_ids={op.id for op in mutable} | guarded_ids,
        payload_validation_operations=operations, freeze_meta=freeze_meta,
        algo_ops_to_schedule=to_schedule, downtime_meta=downtime_meta, resource_pool_meta=pool_meta,
        downtime_map=downtime, resource_pool=pool, optimizer_seed_version=seed_version,
        normalized_input=settings, dispositions=dispositions,
        operation_efforts=efforts,
        preflight_facts=facts, execution_reservations=reservations,
        latest_plan_rows=facts.latest_plan_rows(prev_version),
        operation_sources={op.id: op.source for op in operations},
        piece_scope=piece_scope,
    )


def _algorithm_scope(facts, batches, operations, mutable, guarded_ids, cycles, releases):
    guarded = [op for op in operations if op.id in guarded_ids]
    external_contexts = verified_external_contexts(facts.tables, batches, mutable + guarded)
    algo_ops = build_algo_operations(mutable + guarded, external_contexts=external_contexts)
    for op in algo_ops:
        if op.id not in guarded_ids:
            op.material_ready_date = releases[op.id]
    # Derived peers are fixed for calculation, but must still take part in the
    # original lock/freeze lookup so their inherited locks cannot be overwritten.
    runtime_mutable = mutable + [op for op in guarded if op.id in cycles]
    return algo_ops, runtime_mutable


def _missing_internal_resources(operations):
    return {op.id for op in operations if op.source == "internal" and (op.machine_id is None or op.operator_id is None)}
