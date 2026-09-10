"""Prepare strictly scoped candidate input; never call the legacy run collector."""

import time
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any, Dict, List, Sequence

from core.models.workbench_execution import ExecutionProjection
from core.models.workbench_preflight import local_date, normalize_preflight_input
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    build_execution_resource_reservations,
)
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_input_collector import ScheduleRunInput
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.preflight_facts import PreflightFacts

from .run_input_config import candidate_config
from .run_input_execution import execution_guards
from .run_input_external import prime_template_cache
from .run_input_piece import input_piece_scope, piece_seed_metadata
from .run_input_projection_codec import validate_projection_dto
from .run_input_readonly import candidate_read_snapshot
from .run_input_rows import batch_model, classify_rows, fail, operation_model, validate_single_chain
from .run_input_runtime import build_runtime


@dataclass
class CandidateRunInput(ScheduleRunInput):
    normalized_input: Dict[str, Any] = field(default_factory=dict)
    dispositions: List[Dict[str, Any]] = field(default_factory=list)
    facts_fingerprint: str = ""


def _projection_map(execution_projections, selected_refs):
    if not isinstance(execution_projections, (list, tuple)):
        fail("execution_projection_type", "Supply AJ ExecutionProjection objects, not a reconstructed dictionary.")
    result = {}
    for projection in execution_projections:
        if not isinstance(projection, ExecutionProjection):
            fail("execution_projection_type", "Every execution item must be an AJ ExecutionProjection.")
        validate_projection_dto(projection)
        if projection.operation_ref in result:
            fail("execution_projection_duplicate", "Execution projection identity is duplicated.")
        result[projection.operation_ref] = projection
    if not set(selected_refs) <= set(result):
        fail("execution_projection_missing", "Execution projection does not cover every selected operation.")
    return result


def prepare_candidate_run_input(conn, normalized_input: Dict[str, Any],
                                execution_projections: Sequence[ExecutionProjection]) -> CandidateRunInput:
    """Read-only. Caller supplies AJ selected + all last-official execution scope.

    The worker owns the existing run lock and its admission/final revalidation.
    This function neither acquires that lock nor accepts/publishes a run.
    """
    settings = normalize_preflight_input(normalized_input)
    if not settings["batch_refs"]:
        fail("empty_scope", "An empty batch selection is not a request for all batches.")
    with candidate_read_snapshot(conn):
        facts = PreflightFacts(conn)
        with facts.snapshot() as fingerprint:
            raw_batches = facts.selected(settings["batch_refs"])
            batches = {row["batch_id"]: batch_model(row) for row in raw_batches}
            raw_ops = [row for row in facts.tables["BatchOperations"] if row["batch_id"] in batches]
            operations = [operation_model(row) for row in raw_ops]
            projections = _projection_map(execution_projections, [facts.operation_ref(row) for row in raw_ops])
            return _prepare(conn, settings, facts, fingerprint, raw_batches, batches, operations, projections)


def _prepare(conn, settings, facts, fingerprint, raw_batches, batches, operations, projections):
    piece_scope = input_piece_scope(operations, batches)
    if piece_scope is None:
        validate_single_chain(operations)
    svc = ScheduleService(conn)
    cfg = candidate_config(conn, settings)
    if piece_scope is not None:
        cfg = replace(cfg, dispatch_mode="sgs")
    prev_version = svc.history_repo.get_latest_version()
    start = datetime.combine(local_date(settings["start_date"]), datetime.min.time())
    guards = execution_guards(svc, facts, operations, batches, projections, prev_version, piece_scope=piece_scope)
    execution_facts, fixed, completed, execution_seeds, revisions, snapshot = guards
    dispositions, mutable = classify_rows(facts, settings, raw_batches, operations, projections,
                                         set(fixed) | set(completed), piece_scope=piece_scope)
    guarded = [op for op in operations if op.id in set(fixed) | set(completed)]
    prime_template_cache(svc, facts.tables, batches, mutable + guarded)
    algo_outcome = build_algo_operations(svc, mutable + guarded, strict_mode=True, return_outcome=True)
    reservations = build_execution_resource_reservations(
        svc, facts=execution_facts, selected_op_ids={op.id for op in operations}, start_dt=start,
    )
    calendar = CalendarService(conn)
    if reservations:
        calendar = ExecutionResourceCalendar(calendar, reservations)
    runtime = build_runtime(
        svc, cfg=cfg, prev_version=prev_version, start_dt=start, batches=batches, operations=operations,
        mutable=mutable, algo_ops=algo_outcome.value, fixed_ids=fixed, completed_ids=completed,
        execution_seeds=execution_seeds, reservations=reservations,
    )
    frozen, seeds, warnings, freeze_meta, to_schedule, downtime_meta, pool_meta, downtime, pool, seed_version = runtime
    if piece_scope is not None:
        seeds = piece_seed_metadata(seeds, algo_outcome.value)
    missing_ids = _missing_internal_resources(mutable)
    return CandidateRunInput(
        normalized_batch_ids=[row["batch_id"] for row in raw_batches], start_dt_norm=start,
        end_date_norm=local_date(settings["end_date"]), created_by_text="system", run_label="candidate computation",
        t0=time.time(), cal_svc=calendar, cfg_svc=None, cfg=cfg, readiness_gate_enabled=settings["ready_check"],
        batches=batches, operations=operations, reschedulable_operations=mutable,
        reschedulable_op_ids={op.id for op in mutable}, missing_internal_resource_op_ids=missing_ids,
        algo_input_outcome=algo_outcome, algo_ops=algo_outcome.value, prev_version=prev_version,
        frozen_op_ids=frozen, seed_results=seeds, execution_facts=execution_facts,
        execution_fixed_op_ids=fixed, execution_completed_op_ids=completed, execution_seed_results=execution_seeds,
        execution_guard_state_revisions=revisions, execution_snapshot_revision=snapshot.revision,
        execution_snapshot_op_ids=list(snapshot.op_ids), execution_snapshot_op_count=snapshot.op_count,
        execution_has_guarded_facts=bool(fixed or completed or reservations),
        schedule_output_allowed_op_ids={op.id for op in mutable} | set(fixed) | set(completed),
        payload_validation_operations=operations, algo_warnings=warnings, freeze_meta=freeze_meta,
        algo_ops_to_schedule=to_schedule, downtime_meta=downtime_meta, resource_pool_meta=pool_meta,
        downtime_map=downtime, resource_pool=pool, optimizer_seed_version=seed_version,
        normalized_input=settings, dispositions=dispositions, facts_fingerprint=fingerprint,
    )


def _missing_internal_resources(operations):
    return {op.id for op in operations if op.source == "internal" and (op.machine_id is None or op.operator_id is None)}
