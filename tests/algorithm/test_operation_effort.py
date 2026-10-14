"""Runtime preparation decomposition must equal the actual slot requirement."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.algorithm_runtime.piece_input import operation_batch


class FixedEfficiencyCalendar:
    def adjust_to_working_time(self, value, **kwargs):
        return value

    def get_efficiency(self, value, **kwargs):
        return 0.5

    def add_working_hours(self, value, hours, **kwargs):
        return value + timedelta(hours=hours)


@pytest.mark.parametrize("piece,setup,unit,quantity,required", [
    (None, 2, 0.5, 10, 7), ("piece-1", 2, 0.5, 10, 2.5), (None, 0, 0, 10, 0), (None, 2, 0.5, 0, 2),
])
def test_effort_matches_slot_and_keeps_standard_hours_before_efficiency(piece, setup, unit, quantity, required):
    op = SimpleNamespace(id=1, batch_id="B1", piece_id=piece, setup_hours=setup, unit_hours=unit)
    batch = SimpleNamespace(quantity=quantity, priority="normal")
    work = operation_batch(op, batch)
    effort = internal_operation_effort(op, batch, remaining_quantity=work.quantity)
    start = datetime(2026, 10, 13, 8)
    slot = estimate_internal_slot(
        calendar=FixedEfficiencyCalendar(), op=op, batch=work, machine_id="M1", operator_id="O1",
        base_time=start, prev_end=start, machine_timeline=[], operator_timeline=[], end_dt_exclusive=None,
        machine_downtimes=[], last_op_type_by_machine={}, abort_after=None,
    )
    assert effort.required_standard_hours == validate_internal_hours(op, work) == required
    assert effort.setup_standard_hours == setup
    assert effort.processing_standard_hours == required - setup
    assert slot.end_time - slot.start_time == timedelta(hours=required * 2)
    assert slot.total_hours == required * 2
    assert effort.setup_state == "pending" and effort.effort_basis == "runtime_requirement_v1"
    assert effort.quantity_basis == ("piece" if piece else "batch")
    assert effort.target_quantity == effort.remaining_quantity == work.quantity
    assert type(effort.target_quantity) is int
    assert batch.quantity == quantity


def test_external_merged_cycle_is_separate_from_internal_preparation():
    op = SimpleNamespace(id=4, batch_id="B1", piece_id="piece-2", setup_hours=None, unit_hours=None,
                         ext_merge_mode="merged", ext_group_id="G1", ext_group_total_days=3, ext_days=None)
    effort = external_operation_effort(op, SimpleNamespace(quantity=10))
    assert effort.setup_standard_hours == effort.processing_standard_hours == effort.required_standard_hours == 0
    assert effort.external_cycle_days == 3 and effort.external_group_id == "G1"
    assert effort.external_merge_mode == "merged" and effort.setup_state == "external"
    assert effort.target_quantity == 1 and effort.quantity_basis == "piece"
