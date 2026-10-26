"""Preserved arrangements use saved requirements, while pending slots use runtime input."""

from copy import deepcopy
from datetime import datetime

from core.algorithm_runtime.operation_effort import internal_operation_effort
from core.models.workbench_execution import ExecutionProjection
from core.services.scheduler.execution.execution_fact_provider import ExecutionFact
from core.services.scheduler.run.operation_effort import build_operation_efforts
from tests._support.algo_operations import make_algo_op, make_batch, make_batch_operation


def operation(op_id, *, piece=None, setup=2, unit=0.5):
    return make_algo_op(id=op_id, piece_id=piece, setup_hours=setup, unit_hours=unit)


def row(op):
    """The batch operation row that the algorithm input was built from."""
    return make_batch_operation(id=op.id, piece_id=op.piece_id, setup_hours=op.setup_hours, unit_hours=op.unit_hours)


def projection(*, target=10, basis="batch", remaining=10, state="unreported", first_start=None):
    """The run input reads one execution projection for every selected operation."""
    return ExecutionProjection(
        operation_ref="1" * 48, current_task_ref=None, comparison_task_ref=None, plan_identity=None,
        target_quantity=target, target_basis=basis, known_completed_quantity=target - remaining,
        quantity_complete=True, unknown_record_count=0, records_complete=True, first_actual_start=first_start,
        confirmed_finish=None, execution_state=state, completion_basis=None, data_quality="complete",
        remaining_quantity=remaining,
    )


def test_actual_slot_seed_and_skipped_roles_preserve_their_own_evidence():
    ops = [operation(1), operation(2), operation(3), operation(4), operation(5), operation(6, piece="P6")]
    rows = [row(op) for op in ops]
    batch = make_batch(quantity=10)
    saved = internal_operation_effort(ops[1], batch).to_dict()
    original = deepcopy(saved)
    # A current template edit must not rewrite the retained arrangement's original requirement.
    ops[1].setup_hours = ops[1].unit_hours = rows[1].setup_hours = rows[1].unit_hours = 99
    projections = {1: projection(), 2: projection(), 5: projection(),
                   3: projection(remaining=6, state="partial", first_start="2026-10-13T08:00:00"),
                   4: projection(remaining=0, state="complete", first_start="2026-10-13T08:00:00"),
                   6: projection(target=1, basis="piece", remaining=1)}
    seeds = [{"op_id": 2}, {"op_id": 3, "seed_source": "execution_fact"},
             {"op_id": 4, "seed_source": "execution_fact"}]
    efforts = build_operation_efforts(
        operations=rows, batches={"B1": batch}, algo_operations=ops,
        operations_to_schedule=[ops[0], ops[5]], seed_results=seeds,
        execution_facts={}, execution_projections=projections, saved_efforts={2: saved},
    )
    by_id = {row.op_id: row for row in efforts}
    assert len(by_id) == len(efforts) == 6
    assert by_id[1].required_standard_hours == 7 and by_id[1].requirement_role == "new_schedule"
    assert by_id[6].required_standard_hours == 2.5 and by_id[6].target_quantity == 1
    assert by_id[2].required_standard_hours == 7 and by_id[2].setup_state == "pending"
    assert by_id[2].requirement_role == "retained" and saved == original
    assert by_id[3].requirement_role == "execution" and by_id[3].setup_state == "unknown"
    assert by_id[3].target_quantity is None and by_id[3].quantity_basis == "unknown"
    assert by_id[3].execution_target_quantity == 10 and by_id[3].execution_quantity_basis == "batch"
    assert by_id[3].remaining_quantity == 6
    assert by_id[3].setup_standard_hours is by_id[3].processing_standard_hours is by_id[3].required_standard_hours is None
    assert by_id[3].data_gaps[0]["code"] == "runtime_requirement_missing"
    assert by_id[4].requirement_role == "completed" and by_id[4].setup_state == "already_completed"
    assert by_id[4].required_standard_hours is None and by_id[4].remaining_quantity == 0
    assert by_id[5].requirement_role == "not_scheduled" and by_id[5].required_standard_hours is None


def test_execution_seed_can_retain_authenticated_saved_decomposition_without_recharging_setup():
    op = operation(1)
    batch = make_batch(quantity=10)
    saved = internal_operation_effort(op, batch).to_dict()
    fact = ExecutionFact(op_id=1, batch_id="B1", actual_status="processing", actual_start_time=datetime(2026, 10, 13, 8),
                         actual_end_time=None, actual_machine_id=None, actual_operator_id=None, state_revision="r1")
    efforts = build_operation_efforts(
        operations=[row(op)], batches={"B1": batch}, algo_operations=[op], operations_to_schedule=[],
        seed_results=[{"op_id": 1, "seed_source": "execution_fact"}], execution_facts={1: fact},
        execution_projections={1: projection(remaining=6, state="partial", first_start="2026-10-13T08:00:00")},
        saved_efforts={1: saved},
    )
    effort = efforts[0]
    assert effort.setup_standard_hours == 2 and effort.processing_standard_hours == 5 and effort.required_standard_hours == 7
    assert effort.requirement_role == "execution" and effort.setup_state == "retained_in_execution"
    assert effort.target_quantity == 10 and effort.quantity_basis == "batch" and effort.remaining_quantity == 6
    assert effort.execution_target_quantity == 10 and effort.execution_quantity_basis == "batch"
    assert saved["setup_state"] == "pending"


def test_retained_demand_target_stays_with_saved_decomposition_after_current_target_changes():
    op = operation(1)
    saved = internal_operation_effort(op, make_batch(quantity=10)).to_dict()
    effort = build_operation_efforts(
        operations=[row(op)], batches={"B1": make_batch(quantity=20)}, algo_operations=[op],
        operations_to_schedule=[], seed_results=[{"op_id": 1}], execution_facts={},
        execution_projections={1: projection(target=20, remaining=20)}, saved_efforts={1: saved},
    )[0]
    assert effort.requirement_role == "retained" and effort.required_standard_hours == 7
    assert effort.target_quantity == 10 and effort.quantity_basis == "batch"
    assert effort.execution_target_quantity == effort.remaining_quantity == 20 and effort.execution_quantity_basis == "batch"
    assert saved["target_quantity"] == 10 and saved["required_standard_hours"] == 7
