"""EC lower-layer fixtures, not candidate/trial entrypoint or worker bypasses.

All inputs come from a fresh current-schema SQLite database. slot_payload uses
the real internal slot/calendar engine with explicit per-operation work, while
greedy_payload exposes the unmodified real GreedyScheduler's results.
"""

from datetime import datetime
from types import SimpleNamespace

from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.algorithms.greedy.scheduler import GreedyScheduler
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_guardrails import _collect_execution_guardrails
from core.services.scheduler.run.schedule_input_builder import build_algo_operations
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results
from core.services.scheduler.schedule_service import ScheduleService
from core.services.workbench.piece_adoption_scope import build_piece_adoption_scope
from core.services.workbench.run_input_config import candidate_config
from core.services.workbench.run_input_external import prime_template_cache
from core.services.workbench.run_input_rows import batch_model, operation_model
from core.services.workbench.run_input_runtime import _locked_seeds
from data.repositories.workbench_plan_identity_repo import WorkbenchPlanIdentityRepository
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
    batches = {key: batch_model(dict(case.conn.execute("SELECT * FROM Batches WHERE batch_id=?", (key,)).fetchone()))
               for key in ids}
    operations = [operation_model(dict(row)) for key in ids for row in case.conn.execute(
        "SELECT * FROM BatchOperations WHERE batch_id=? ORDER BY id", (key,))]
    svc = ScheduleService(case.conn)
    version = svc.history_repo.get_latest_version()
    facts, fixed, completed, actual, revisions, snap = _collect_execution_guardrails(svc, operations, prev_version=version)
    refs = WorkbenchPlanIdentityRepository(case.conn).get_operation_refs(op.id for op in operations)
    projected = {item.operation_ref: item.to_dict() for item in case.projections(*ids)}
    scope = build_piece_adoption_scope(operations, batches)
    dispositions = [{"op_id": work.op_id, "operation_ref": refs[work.op_id], "batch_id": work.batch_id,
                     "batch_ref": case.ref("batch", work.batch_id), "piece_id": work.piece_id,
                     "sequence": work.sequence, "predecessor_refs": [refs[key] for key in work.predecessor_op_ids],
                     "status": "protected" if work.op_id in fixed | completed else "eligible", "issues": [],
                     "execution": projected[refs[work.op_id]]} for work in scope.operations]
    locks = _locked_seeds(svc, [op for op in operations if op.id not in fixed | completed], version)
    tables = {name: [dict(row) for row in case.conn.execute('SELECT * FROM "' + name + '"')]
              for name in ("PartOperations", "ExternalGroups")}
    prime_template_cache(svc, tables, batches, operations)
    return SimpleNamespace(normalized_batch_ids=ids, normalized_input=case.settings(*ids),
        operations=operations, batches=batches, dispositions=dispositions,
        cal_svc=CalendarService(case.conn), prev_version=version, start_dt_norm=START,
        cfg=candidate_config(case.conn, case.settings(*ids)),
        end_date_norm=datetime(2026, 9, 25).date(), readiness_gate_enabled=True, downtime_map={},
        algo_ops=build_algo_operations(svc, operations, strict_mode=True),
        frozen_op_ids={row["op_id"] for row in locks}, seed_results=actual + locks,
        execution_facts=facts, execution_fixed_op_ids=fixed, execution_completed_op_ids=completed,
        execution_seed_results=actual, execution_guard_state_revisions=revisions,
        execution_snapshot_revision=snap.revision, execution_snapshot_op_ids=list(snap.op_ids),
        execution_snapshot_op_count=snap.op_count, schedule_output_allowed_op_ids={op.id for op in operations})


def payload(prepared, results):
    return build_validated_schedule_payload(results, allowed_op_ids=prepared.schedule_output_allowed_op_ids,
                                            operations=prepared.operations)


def slot_payload(prepared, *, placements=None):
    """Real slot-engine results, never a claim of a completed production run."""
    placements = placements or {}
    scope = build_piece_adoption_scope(prepared.operations, prepared.batches)
    work = {row.op_id: row for row in scope.operations}
    result = {seed["op_id"]: SimpleNamespace(**seed) for seed in prepared.seed_results}
    for op in sorted(prepared.operations, key=lambda item: (item.seq, item.id)):
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
        assert not slot.efficiency_fallback_used
        result[op.id] = SimpleNamespace(op_id=op.id, machine_id=op.machine_id, operator_id=op.operator_id,
            start_time=slot.start_time, end_time=slot.end_time, source=op.source)
    return payload(prepared, list(result.values()))


def greedy_payload(prepared):
    scope = build_piece_adoption_scope(prepared.operations, prepared.batches)
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
