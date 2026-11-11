"""EC lower-layer fixtures, not candidate/trial entrypoint or worker bypasses.

All inputs come from a fresh current-schema SQLite database and the production
prepared input. slot_payload uses the real internal slot/calendar engine with
explicit per-operation work.
"""

from datetime import datetime

from core.algorithm_runtime.algo_stats import make_algo_stats
from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.services.scheduler.run.schedule_payload_contract import build_validated_schedule_payload
from core.services.scheduler.run.schedule_seed_contracts import coerce_seed_results
from core.services.workbench.facts.piece_scope import build_piece_adoption_scope
from core.services.workbench.facts.zero_duration import candidate_point_validator
from core.services.workbench.run.input_runtime import runtime_resource_inputs
from tests._support.algo_operations import make_schedule_result
from tests.workbench.run_candidate_adoption_support import snapshot
from tests.workbench.run_candidate_support import candidate_case as candidate_case  # noqa: F401
from tests.workbench.run_compute_support import prepare_run_input

START = datetime(2026, 9, 9, 8)


def split(case):
    """Use explicit split stages, with two stages per piece and common ends."""
    unit = 0.25
    quantity = 3
    case.conn.execute("UPDATE Batches SET quantity=? WHERE batch_id='B1'", (quantity,))
    case.conn.execute("UPDATE BatchOperations SET seq=10,unit_hours=? WHERE id=?", (unit, case.op_id))
    ops = {(None, 10): case.op_id}
    for piece in ("item-A", "item-B", "item-C"):
        for seq in (20, 30):
            ops[piece, seq] = case.operation(seq=seq, piece_id=piece, op_code=piece + "-" + str(seq), unit_hours=unit)
    ops[None, 40] = case.operation(seq=40, unit_hours=unit)
    case.conn.commit()
    return ops


def lower_input(case, *batch_ids):
    """The production prepared input for the selected batches, read in its own snapshot."""
    ids = batch_ids or ("B1",)
    return prepare_run_input(case.conn, case.settings(*ids), case.projections(*ids))


def slot_payload(prepared, *, placements=None):
    """Real slot-engine results, never a claim of a completed production run."""
    placements = placements or {}
    scope = build_piece_adoption_scope(prepared.operations, {key: batch.quantity for key, batch in prepared.batches.items()})
    work = {row.op_id: row for row in scope.operations}
    downtimes = runtime_resource_inputs(prepared.facts).downtimes
    result = {row.op_id: row for row in coerce_seed_results(prepared.seeds.seed_results, optimizer_algo_stats=make_algo_stats())}
    for op in sorted(prepared.algo_ops, key=lambda item: (item.seq, item.id)):
        if op.id in result:
            continue
        target = work[op.id]
        batch = prepared.batches[op.batch_id]
        previous = max([result[key].end_time for key in target.predecessor_op_ids] or [prepared.start])
        slot = estimate_internal_slot(
            calendar=prepared.facts.calendar(
                frozenset(op.operator_id for op in prepared.operations if op.operator_id is not None)
            ),
            op=op, batch=batch,
            machine_id=op.machine_id, operator_id=op.operator_id,
            base_time=placements.get(op.id, prepared.start), prev_end=previous,
            machine_timeline=[(row.start_time, row.end_time) for row in result.values() if row.machine_id == op.machine_id],
            operator_timeline=[(row.start_time, row.end_time) for row in result.values() if row.operator_id == op.operator_id],
            machine_downtimes=downtimes.get(op.machine_id, ()), end_dt_exclusive=None,
            last_op_type_by_machine=None, abort_after=None,
            total_hours_base=op.setup_hours + op.unit_hours * target.target_quantity)
        result[op.id] = make_schedule_result(op_id=op.id, op_code=op.op_code, batch_id=op.batch_id, seq=op.seq,
            machine_id=op.machine_id, operator_id=op.operator_id, start_time=slot.start_time, end_time=slot.end_time,
            source=op.source, op_type_name=op.op_type_name, op_type_id=op.op_type_id)
    return build_validated_schedule_payload(
        list(result.values()),
        allowed_op_ids=prepared.allowed_op_ids,
        operations=prepared.operations,
        operation_sources=prepared.operation_sources,
        missing_internal_resource_op_ids=prepared.missing_internal_resource_op_ids,
        point_validator=candidate_point_validator(prepared),
    ).schedule_rows


def checked_read_only(case, function):
    before, changes = snapshot(case.conn), case.conn.total_changes
    try:
        return function()
    finally:
        assert snapshot(case.conn) == before
        assert case.conn.total_changes == changes
