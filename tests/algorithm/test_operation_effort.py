"""Runtime preparation decomposition must equal the actual slot requirement."""

import sys
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace
from unittest.mock import MagicMock

import pytest

from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.algorithm_runtime.piece_input import operation_batch
from core.algorithms.greedy.dispatch.batch_order import _dispatch_one
from core.algorithms.ortools_bottleneck import OrtoolsWarmstartError, try_solve_bottleneck_batch_order


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


@pytest.fixture
def cp_boundary(monkeypatch):
    """Exercise production load aggregation without requiring the optional solver."""
    intervals, starts = [], {}
    model, solver = MagicMock(), MagicMock()

    def variable(low, high, name):
        value = MagicMock(name=name)
        value.__ge__.return_value = True
        return value

    def interval(start, duration, end, name):
        item = SimpleNamespace(start=start, duration=duration)
        intervals.append(item)
        return item

    def solve(problem):
        elapsed = 0
        for item in sorted(intervals, key=lambda item: item.duration):
            starts[item.start] = elapsed
            elapsed += item.duration
        return 4

    model.NewIntVar.side_effect = variable
    model.NewIntervalVar.side_effect = interval
    solver.Solve.side_effect = solve
    solver.Value.side_effect = starts.__getitem__
    cp_model = SimpleNamespace(CpModel=lambda: model, CpSolver=lambda: solver,
                               OPTIMAL=4, FEASIBLE=2, INFEASIBLE=3, MODEL_INVALID=1, UNKNOWN=0)
    for name in ("ortools", "ortools.sat", "ortools.sat.python"):
        monkeypatch.setitem(sys.modules, name, ModuleType(name))
    monkeypatch.setitem(sys.modules, "ortools.sat.python.cp_model", cp_model)
    return intervals


def _warmstart_op(op_id, batch_id, *, piece=None, op_type="turning", setup=0, unit=1):
    return SimpleNamespace(id=op_id, op_code=f"OP{op_id}", batch_id=batch_id, piece_id=piece, op_type_id=op_type,
                           source="internal", setup_hours=setup, unit_hours=unit)


def test_warmstart_aggregates_piece_load_and_reads_solver_order(cp_boundary):
    batches = {"B1": SimpleNamespace(quantity=20), "B2": SimpleNamespace(quantity=2)}
    ops = [_warmstart_op(index, "B1", piece=f"P{index}") for index in range(20)]
    ops += [_warmstart_op(20 + index, "B2", piece=f"Q{index}") for index in range(2)]
    order = try_solve_bottleneck_batch_order(operations=ops, batches=batches, start_dt=datetime(2026, 10, 13))
    assert [item.duration for item in cp_boundary] == [20 * 60, 2 * 60]
    assert order == ["B2", "B1"]
    assert batches["B1"].quantity == 20 and batches["B2"].quantity == 2


def test_warmstart_selects_bottleneck_by_effective_piece_work(cp_boundary):
    batches = {
        "B1": SimpleNamespace(quantity=20),
        "B2": SimpleNamespace(quantity=2),
        "B_LATE": SimpleNamespace(quantity=1, due_date="2026-10-20"),
        "B_EARLY": SimpleNamespace(quantity=1, due_date="2026-10-14"),
    }
    ops = [_warmstart_op(index, "B1", piece=f"P{index}") for index in range(20)]
    ops += [_warmstart_op(20, "B1", op_type="grinding", unit=0.1),
            _warmstart_op(21, "B2", op_type="grinding", unit=12.5),
            _warmstart_op(22, "B_LATE", op_type="turning", unit=0.5),
            _warmstart_op(23, "B_EARLY", op_type="turning", unit=0.5)]
    order = try_solve_bottleneck_batch_order(operations=ops, batches=batches, start_dt=datetime(2026, 10, 13))
    # Grinding is 27 hours; turning is 21 hours, rather than 20 * 20. Non-bottleneck batches sort by real due date.
    assert [item.duration for item in cp_boundary] == [2 * 60, 25 * 60]
    assert order == ["B1", "B2", "B_EARLY", "B_LATE"]


@pytest.mark.parametrize("field,value", [
    ("setup_hours", True), ("unit_hours", False), ("quantity", True),
    ("setup_hours", float("inf")), ("unit_hours", float("nan")), ("quantity", float("inf")),
    ("setup_hours", -1), ("unit_hours", -1), ("quantity", -1),
])
def test_internal_and_warmstart_reject_invalid_component_values(cp_boundary, field, value):
    op, batch = _warmstart_op(1, "B1", setup=2), SimpleNamespace(quantity=10)
    if field == "quantity":
        batch.quantity = value
    elif field == "setup_hours":
        op.setup_hours = value
    else:
        op.unit_hours = value
    with pytest.raises(ValueError):
        internal_operation_effort(op, batch)
    with pytest.raises(ValueError):
        validate_internal_hours(op, batch)
    with pytest.raises(OrtoolsWarmstartError):
        try_solve_bottleneck_batch_order(operations=[op], batches={"B1": batch}, start_dt=datetime(2026, 10, 13))
    assert not cp_boundary


@pytest.mark.parametrize("source,callback", [("internal", "schedule_internal"), ("external", "schedule_external")])
def test_batch_order_dispatch_supplies_required_operation_input(source, callback):
    op, batch = _warmstart_op(1, "B1", piece="P1"), SimpleNamespace(quantity=20)
    op.source = source
    ctx, state = MagicMock(), MagicMock()
    _dispatch_one(
        ctx, op=op, batches={"B1": batch}, state=state, base_time=datetime(2026, 10, 13),
        end_dt_exclusive=None, machine_downtimes={}, auto_assign_enabled=False, resource_pool=None, strict_mode=False,
    )
    sent = ctx.schedule_internal.call_args if callback == "schedule_internal" else ctx.schedule_external.call_args
    if source == "internal":
        assert sent.kwargs["batch"].quantity == 1
    else:
        assert "batch" not in sent.kwargs
    assert batch.quantity == 20


def test_piece_operation_dispatch_state_prev_end_uses_operation_release_floor():
    from core.algorithm_runtime.piece_input import operation_dispatch_state
    from core.algorithm_runtime.run_state import ScheduleRunState

    base = datetime(2026, 10, 13, 8, 0)
    piece_end = datetime(2026, 10, 13, 10, 0)
    batch_end = datetime(2026, 10, 13, 16, 0)
    state = ScheduleRunState(base_time=base)
    state.batch_progress["B1"] = batch_end
    graph_state = {
        "end_time_by_op_id": {1: piece_end},
        "predecessor_op_ids_by_op_id": {2: {1}, 3: set()},
    }
    batch = SimpleNamespace(quantity=2, ready_date=None)
    dependent = operation_dispatch_state(state, graph_state, SimpleNamespace(id=2, batch_id="B1"), batch)
    independent = operation_dispatch_state(state, graph_state, SimpleNamespace(id=3, batch_id="B1"), batch)
    assert dependent.prev_end("B1") == piece_end
    assert independent.prev_end("B1") == base
    assert state.prev_end("B1") == batch_end


def _external_op(*, merged, total_days=3, material_ready_date="2026-10-16"):
    return SimpleNamespace(id=5, op_code="EXT", batch_id="B1", seq=1, source="external", op_type_name=None,
                           material_ready_date=material_ready_date, ext_days=2,
                           ext_merge_mode="merged" if merged else None, ext_group_id="G1" if merged else None,
                           ext_group_total_days=total_days if merged else None)


class _NaturalDayCalendar:
    def add_calendar_days(self, value, days):
        return value + timedelta(days=days)


@pytest.mark.parametrize("merged", [False, True])
def test_external_candidate_window_waits_for_material_like_the_placement(merged):
    from core.algorithm_runtime.piece_input import external_group_key
    from core.algorithm_runtime.run_state import ScheduleRunState
    from core.algorithms.greedy.dispatch.sgs_due_span import external_candidate_window
    from core.algorithms.greedy.external_groups import schedule_external

    base = datetime(2026, 10, 13, 8)
    op, calendar = _external_op(merged=merged), _NaturalDayCalendar()
    state = ScheduleRunState(base_time=base)
    window = external_candidate_window(SimpleNamespace(calendar=calendar), state, op=op, prev_end=base, strict_mode=True)
    result, blocked = schedule_external(SimpleNamespace(calendar=calendar), op=op, batch_progress={},
                                        external_group_cache={}, base_time=base, errors=[], end_dt_exclusive=None,
                                        strict_mode=True)
    assert not blocked and window == (result.start_time, result.end_time)
    assert window[0] == datetime(2026, 10, 16)
    if merged:
        # An already placed group block is shared as-is, even when it started before this member's material.
        placed = (base, base + timedelta(days=3))
        state.external_group_cache[external_group_key(op)] = placed
        assert external_candidate_window(SimpleNamespace(calendar=calendar), state, op=op, prev_end=base,
                                          strict_mode=True) == placed


def test_merged_external_group_is_cached_only_when_it_fits_the_window():
    from core.algorithm_runtime.piece_input import external_group_key
    from core.algorithms.greedy.external_groups import schedule_external

    base = datetime(2026, 10, 13, 8)
    op, scheduler = _external_op(merged=True, total_days=5, material_ready_date=None), SimpleNamespace(calendar=_NaturalDayCalendar())
    cache, errors = {}, []
    result, blocked = schedule_external(scheduler, op=op, batch_progress={}, external_group_cache=cache, base_time=base,
                                        errors=errors, end_dt_exclusive=base + timedelta(days=2), strict_mode=True)
    assert result is None and blocked and len(errors) == 1
    assert cache == {}
    result, blocked = schedule_external(scheduler, op=op, batch_progress={}, external_group_cache=cache, base_time=base,
                                        errors=errors, end_dt_exclusive=base + timedelta(days=10), strict_mode=True)
    assert result is not None and not blocked
    assert cache == {external_group_key(op): (result.start_time, result.end_time)}
