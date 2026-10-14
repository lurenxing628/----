"""Preserved arrangements use saved requirements, while pending slots use runtime input."""

from copy import deepcopy
from types import SimpleNamespace

from core.algorithm_runtime.operation_effort import internal_operation_effort
from core.services.scheduler.run.operation_effort import build_operation_efforts


def operation(op_id, *, piece=None, setup=2, unit=0.5):
    return SimpleNamespace(id=op_id, batch_id="B1", piece_id=piece, source="internal",
                           setup_hours=setup, unit_hours=unit)


def test_actual_slot_seed_and_skipped_roles_preserve_their_own_evidence():
    ops = [operation(1), operation(2), operation(3), operation(4), operation(5), operation(6, piece="P6")]
    batch = SimpleNamespace(quantity=10)
    saved = internal_operation_effort(ops[1], batch).to_dict()
    original = deepcopy(saved)
    # A current template edit must not rewrite the retained arrangement's original requirement.
    ops[1].setup_hours, ops[1].unit_hours = 99, 99
    projections = {1: SimpleNamespace(target_quantity=10, target_basis="batch", remaining_quantity=10,
                                     execution_state="unreported", first_actual_start=None),
                   3: SimpleNamespace(target_quantity=10, target_basis="batch", remaining_quantity=6,
                                      execution_state="partial", first_actual_start="2026-10-13T08:00:00"),
                   4: SimpleNamespace(target_quantity=10, target_basis="batch", remaining_quantity=0,
                                      execution_state="complete", first_actual_start="2026-10-13T08:00:00")}
    seeds = [{"op_id": 2}, {"op_id": 3, "seed_source": "execution_fact"},
             {"op_id": 4, "seed_source": "execution_fact"}]
    efforts = build_operation_efforts(
        operations=ops, batches={"B1": batch}, algo_operations=ops,
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
    batch = SimpleNamespace(quantity=10)
    saved = internal_operation_effort(op, batch)
    fact = SimpleNamespace(actual_status="processing", actual_start_time="2026-10-13T08:00:00", remaining_quantity=6,
                           target_quantity=10, quantity_basis="batch")
    efforts = build_operation_efforts(
        operations=[op], batches={"B1": batch}, algo_operations=[op], operations_to_schedule=[],
        seed_results=[{"op_id": 1, "seed_source": "execution_fact"}], execution_facts={1: fact}, saved_efforts={1: saved},
    )
    effort = efforts[0]
    assert effort.setup_standard_hours == 2 and effort.processing_standard_hours == 5 and effort.required_standard_hours == 7
    assert effort.requirement_role == "execution" and effort.setup_state == "retained_in_execution"
    assert effort.target_quantity == 10 and effort.quantity_basis == "batch" and effort.remaining_quantity == 6
    assert effort.execution_target_quantity == 10 and effort.execution_quantity_basis == "batch"
    assert saved.setup_state == "pending"


def test_retained_demand_target_stays_with_saved_decomposition_after_current_target_changes():
    op = operation(1)
    saved = internal_operation_effort(op, SimpleNamespace(quantity=10))
    projection = SimpleNamespace(target_quantity=20, target_basis="batch", remaining_quantity=20,
                                 execution_state="unreported", first_actual_start=None)
    effort = build_operation_efforts(
        operations=[op], batches={"B1": SimpleNamespace(quantity=20)}, algo_operations=[op],
        operations_to_schedule=[], seed_results=[{"op_id": 1}], execution_projections={1: projection}, saved_efforts={1: saved},
    )[0]
    assert effort.requirement_role == "retained" and effort.required_standard_hours == 7
    assert effort.target_quantity == 10 and effort.quantity_basis == "batch"
    assert effort.execution_target_quantity == effort.remaining_quantity == 20 and effort.execution_quantity_basis == "batch"
    assert saved.target_quantity == 10 and saved.required_standard_hours == 7
