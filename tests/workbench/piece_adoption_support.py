"""EC lower-layer fixtures, not candidate/trial entrypoint or worker bypasses.

All inputs come from a fresh current-schema SQLite database. slot_payload uses
the real internal slot/calendar engine with explicit per-operation work, while
greedy_payload exposes the unmodified real GreedyScheduler's results.
"""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.repository_bundle import build_schedule_repository_bundle
from core.services.scheduler.run.schedule_execution_guardrails import build_execution_guardrails_from_projections
from core.services.scheduler.run.schedule_execution_reservations import build_execution_resource_reservations
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.run_input_rows import batch_model, operation_model
from core.services.workbench.run.input_config import candidate_config, hold_window
from core.services.workbench.run.input_external import execution_groups, verified_external_contexts
from core.services.workbench.run.input_runtime import held_arrangements
from core.services.workbench.run.jobs_facts import run_execution_projections
from core.services.workbench.run.preflight_facts import PreflightFacts
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
from tests._support.algo_operations import make_schedule_result
from tests.workbench.run_candidate_adoption_support import snapshot
from tests.workbench.run_candidate_support import candidate_case as candidate_case  # noqa: F401

START = datetime(2026, 9, 9, 8)


def split(case, *, common=True, unit=0.25, quantity=3):
    """Use explicit split stages, with two stages per piece and common ends."""
    case.conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='B1'", (quantity,))
    case.conn.execute("UPDATE BatchOperations SET seq=10,unit_hours=? WHERE id=?", (unit, case.op_id))
    ops = {}
    if common:
        ops[None, 10] = case.op_id
    else:
        case.conn.execute("UPDATE BatchOperations SET piece_id='item-A',seq=20 WHERE id=?", (case.op_id,))
        ops["item-A", 20] = case.op_id
    for piece in ("item-A", "item-B", "item-C")[:quantity]:
        for seq in (20, 30):
            if (piece, seq) not in ops:
                ops[piece, seq] = case.operation(seq=seq, piece_id=piece, op_code=piece + "-" + str(seq), unit_hours=unit)
    if common:
        ops[None, 40] = case.operation(seq=40, unit_hours=unit)
    case.conn.commit()
    return ops


def lower_input(case, *batch_ids):
    """Assemble the existing prepared DTO fields at the lower seam, without guards patched out."""
    ids = list(batch_ids or ("B1",))
    settings = case.settings(*ids)
    batches = {key: batch_model(dict(case.conn.execute("SELECT * FROM Batches WHERE batch_id=?", (key,)).fetchone()))
               for key in ids}
    operations = [operation_model(dict(row)) for key in ids for row in case.conn.execute(
        "SELECT * FROM BatchOperations WHERE batch_id=? ORDER BY id", (key,))]
    svc = build_schedule_repository_bundle(case.conn)
    production = PreflightFacts(case.conn)
    with production.snapshot(fingerprint=False):
        production.configuration()
    production.execution_projections.update((item.operation_ref, item) for item in run_execution_projections(
        case.conn, settings, capture=production.capture))
    version = max((row["version"] for row in production.capture.table("ScheduleHistory")), default=0)
    prior_refs = {production.operation_refs[op_id] for op_id in production.latest_plan_rows(version)}
    facts, fixed, completed, actual, snap = build_execution_guardrails_from_projections(svc, operations, prev_version=version,
        execution_projections=[row for row in production.execution_projections.values() if row.operation_ref in prior_refs],
        facts=production, external_groups=execution_groups(production, batches, operations))
    refs = WorkbenchPlanIdentityRepository(case.conn).get_operation_refs(op.id for op in operations if op.id is not None)
    projected = {item.operation_ref: item.to_dict() for item in case.projections(*ids)}
    scope = build_piece_adoption_scope(operations, {key: batch.quantity for key, batch in batches.items()})
    dispositions = [{"op_id": work.op_id, "operation_ref": refs[work.op_id], "batch_id": work.batch_id,
                     "batch_ref": case.ref("batch", work.batch_id), "piece_id": work.piece_id,
                     "sequence": work.sequence, "predecessor_refs": [refs[key] for key in work.predecessor_op_ids],
                     "status": "protected" if work.op_id in fixed | completed else "eligible", "issues": [],
                     "execution": projected[refs[work.op_id]]} for work in scope.operations]
    tables = {name: [dict(row) for row in case.conn.execute('SELECT * FROM "' + name + '"')]
              for name in ("BatchExternalContexts", "BatchOperations")}
    external_contexts = verified_external_contexts(tables, batches, operations)
    cfg = candidate_config(settings, snapshot=production.config_snapshot)
    # 正式计划里的锁定标记不再起作用：受保护的只有报工保护的工序，和本次不重排时段里保持原安排的工序。
    held = held_arrangements(facts=production, cfg=cfg, prev_version=version, start_dt=START,
        reschedulable_operations=[op for op in operations if op.id not in fixed | completed],
        hold_window=hold_window(settings, snapshot=production.config_snapshot)[0])
    return SimpleNamespace(preflight_facts=production, latest_plan_rows=production.latest_plan_rows(version),
        execution_reservations=build_execution_resource_reservations(facts=facts,
            selected_op_ids={op.id for op in operations if op.id is not None}, capture=production.capture),
        operation_sources={op.id: op.source for op in operations},
        normalized_batch_ids=ids, normalized_input=settings,
        operations=operations, batches=batches, dispositions=dispositions, piece_scope=scope,
        cal_svc=CalendarService(case.conn), prev_version=version, start_dt_norm=START, cfg=cfg,
        end_date_norm=datetime(2026, 9, 25).date(), readiness_gate_enabled=True, downtime_map={},
        algo_ops=build_algo_operations(operations, external_contexts=external_contexts),
        frozen_op_ids=held.frozen_op_ids, seed_results=actual + held.seed_results,
        execution_facts=facts, execution_fixed_op_ids=fixed, execution_completed_op_ids=completed,
        execution_seed_results=actual,
        execution_snapshot_revision=snap.revision, execution_snapshot_op_ids=list(snap.op_ids),
        execution_snapshot_op_count=snap.op_count, schedule_output_allowed_op_ids={op.id for op in operations})


def payload(prepared, results):
    return build_validated_schedule_payload(results, allowed_op_ids=prepared.schedule_output_allowed_op_ids,
                                            operations=prepared.operations,
                                            operation_sources=prepared.operation_sources)


def slot_payload(prepared, *, placements=None):
    """Real slot-engine results, never a claim of a completed production run."""
    placements = placements or {}
    scope = build_piece_adoption_scope(prepared.operations, {key: batch.quantity for key, batch in prepared.batches.items()})
    work = {row.op_id: row for row in scope.operations}
    result = {row.op_id: row for row in coerce_seed_results(prepared.seed_results, optimizer_algo_stats={})}
    for op in sorted(prepared.algo_ops, key=lambda item: (item.seq, item.id)):
        if op.id in result:
            continue
        target = work[op.id]
        batch = prepared.batches[op.batch_id]
        previous = max([result[key].end_time for key in target.predecessor_op_ids] or [prepared.start_dt_norm])
        slot = estimate_internal_slot(calendar=prepared.cal_svc, op=op, batch=batch,
            machine_id=op.machine_id, operator_id=op.operator_id,
            base_time=placements.get(op.id, prepared.start_dt_norm), prev_end=previous,
            machine_timeline=[(row.start_time, row.end_time) for row in result.values() if row.machine_id == op.machine_id],
            operator_timeline=[(row.start_time, row.end_time) for row in result.values() if row.operator_id == op.operator_id],
            machine_downtimes=prepared.downtime_map.get(op.machine_id, ()), end_dt_exclusive=None,
            last_op_type_by_machine=None, abort_after=None,
            total_hours_base=op.setup_hours + op.unit_hours * target.target_quantity)
        result[op.id] = make_schedule_result(op_id=op.id, op_code=op.op_code, batch_id=op.batch_id, seq=op.seq,
            machine_id=op.machine_id, operator_id=op.operator_id, start_time=slot.start_time, end_time=slot.end_time,
            source=op.source, op_type_name=op.op_type_name, op_type_id=op.op_type_id)
    return payload(prepared, list(result.values()))


def greedy_payload(prepared):
    scope = build_piece_adoption_scope(prepared.operations, {key: batch.quantity for key, batch in prepared.batches.items()})
    before = {row.op_id: set(row.predecessor_op_ids) for row in scope.operations}
    after = {key: {row for row, predecessors in before.items() if key in predecessors} for key in before}
    fixed = {row["op_id"] for row in prepared.seed_results}
    context = {"enabled": True, "schedulable_op_ids": set(before) - fixed, "fixed_op_ids": fixed,
               "predecessor_op_ids_by_op_id": before, "successor_op_ids_by_op_id": after,
               "sort_key_by_op_id": {op.id: (0, op.seq, op.id) for op in prepared.operations if op.id not in fixed}}
    results, summary, _, _ = GreedyScheduler(prepared.cal_svc, prepared.cfg).schedule(
        prepared.algo_ops, prepared.batches, start_dt=prepared.start_dt_norm,
        end_date=prepared.end_date_norm, dispatch_mode="sgs", strict_mode=True,
        seed_results=coerce_seed_results(prepared.seed_results, optimizer_algo_stats={}),
        graph_ready_context=context)
    assert summary.failed_ops == 0
    return results, payload(prepared, results)


def checked_read_only(case, function):
    before, changes = snapshot(case.conn), case.conn.total_changes
    try:
        return function()
    finally:
        assert snapshot(case.conn) == before
        assert case.conn.total_changes == changes
