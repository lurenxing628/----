"""Runtime preparation decomposition must equal the actual slot requirement."""

import sys
from copy import copy
from datetime import datetime, timedelta
from types import ModuleType, SimpleNamespace
from typing import Optional
from unittest.mock import MagicMock

import pytest

from core.algorithm_runtime.internal_slot import estimate_internal_slot, validate_internal_hours
from core.algorithm_runtime.operation_effort import external_operation_effort, internal_operation_effort
from core.algorithm_runtime.piece_input import operation_batch, operation_quantity
from core.algorithms.greedy.dispatch.batch_order import _dispatch_one
from core.algorithms.ortools_bottleneck import try_solve_bottleneck_batch_order
from tests._support.algo_operations import make_algo_op, make_batch


class FixedEfficiencyCalendar:
    def adjust_to_working_time(self, value, **kwargs):
        return value

    def add_effective_hours(self, value, hours, **kwargs):
        return value + timedelta(hours=hours / 0.5)  # every window works at efficiency 0.5

    def add_calendar_days(self, value, days):
        return value + timedelta(days=days)

    def working_hours_between(self, start, end, **kwargs):
        return (end - start).total_seconds() / 3600


@pytest.mark.parametrize("piece,setup,unit,quantity,required", [
    (None, 2, 0.5, 10, 7), ("piece-1", 2, 0.5, 10, 2.5), (None, 0, 0, 10, 0), (None, 2, 0.5, 0, 2),
])
def test_effort_matches_slot_and_keeps_standard_hours_before_efficiency(piece, setup, unit, quantity, required):
    op = make_algo_op(piece_id=piece, setup_hours=setup, unit_hours=unit)
    batch = make_batch(quantity=quantity)
    work = operation_batch(op, batch)
    effort = internal_operation_effort(op, batch, remaining_quantity=work.quantity)
    assert effort.required_standard_hours is not None
    start = datetime(2026, 10, 13, 8)
    slot = estimate_internal_slot(
        calendar=FixedEfficiencyCalendar(), op=op, batch=work, machine_id="M1", operator_id="O1",
        base_time=start, prev_end=start, machine_timeline=[], operator_timeline=[], end_dt_exclusive=None,
        machine_downtimes=[], last_op_type_by_machine=None, abort_after=None,
        total_hours_base=effort.required_standard_hours,
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
    op = make_algo_op(id=4, piece_id="piece-2", source="external", setup_hours=0.0, unit_hours=0.0,
                      ext_merge_mode="merged", ext_group_id="G1", ext_group_total_days=3)
    effort = external_operation_effort(op, make_batch(quantity=10))
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


def _warmstart_op(op_id, batch_id, *, piece=None, op_type="turning", setup: float = 0, unit: float = 1):
    return make_algo_op(id=op_id, batch_id=batch_id, piece_id=piece, op_type_id=op_type, op_type_name=op_type,
                        setup_hours=setup, unit_hours=unit)


def test_warmstart_aggregates_piece_load_and_reads_solver_order(cp_boundary):
    batches = {"B1": make_batch(batch_id="B1", quantity=20), "B2": make_batch(batch_id="B2", quantity=2)}
    ops = [_warmstart_op(index, "B1", piece=f"P{index}") for index in range(20)]
    ops += [_warmstart_op(20 + index, "B2", piece=f"Q{index}") for index in range(2)]
    order = try_solve_bottleneck_batch_order(operations=ops, batches=batches, start_dt=datetime(2026, 10, 13))
    assert [item.duration for item in cp_boundary] == [20 * 60, 2 * 60]
    assert order == ["B2", "B1"]
    assert batches["B1"].quantity == 20 and batches["B2"].quantity == 2


def test_warmstart_selects_bottleneck_by_effective_piece_work(cp_boundary):
    batches = {
        "B1": make_batch(batch_id="B1", quantity=20),
        "B2": make_batch(batch_id="B2", quantity=2),
        "B_LATE": make_batch(batch_id="B_LATE", quantity=1, due_date="2026-10-20"),
        "B_EARLY": make_batch(batch_id="B_EARLY", quantity=1, due_date="2026-10-14"),
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


@pytest.mark.parametrize("source,callback", [("internal", "schedule_internal"), ("external", "schedule_external")])
def test_batch_order_dispatch_supplies_required_operation_input(source, callback):
    op, batch = _warmstart_op(1, "B1", piece="P1"), make_batch(quantity=20)
    op.source = source
    ctx, state = MagicMock(), MagicMock()
    ctx.native_preparation.operation_batch.side_effect = operation_batch
    ctx.schedule_internal.return_value = ctx.schedule_external.return_value = (None, {"code": "schedule_window_exceeded"})
    _dispatch_one(
        ctx, op=op, batches={"B1": batch}, state=state, base_time=datetime(2026, 10, 13),
        end_dt_exclusive=None, machine_downtimes={}, auto_assign_enabled=False, resource_pool=None,
    )
    sent = ctx.schedule_internal.call_args if callback == "schedule_internal" else ctx.schedule_external.call_args
    if source == "internal":
        assert ctx.native_preparation.operation_batch.call_count == 1
        assert sent.kwargs["batch"].quantity == 1
    else:
        assert ctx.native_preparation.operation_batch.call_count == 0
        assert "batch" not in sent.kwargs
    assert batch.quantity == 20


@pytest.mark.parametrize("source", ["external", "internal"])
def test_sgs_candidate_scoring_skips_piece_operation_batch_for_external(monkeypatch, source):
    from core.algorithms.greedy import schedule_preparation as prep_module
    from core.algorithms.greedy.scheduler import GreedyScheduler
    from core.services.scheduler.run.optimizer.shared_decode import decode_and_metrics
    from tests._support.schedule_decode import config_snapshot, production_session

    copied = MagicMock(side_effect=operation_batch)
    monkeypatch.setattr(prep_module, "operation_batch", copied)
    batch = make_batch(batch_id="B1", quantity=20)
    if source == "external":
        op = make_algo_op(
            id=1, batch_id="B1", piece_id="P1", op_code="EXT", source="external",
            setup_hours=0.0, unit_hours=0.0, ext_days=2.0,
        )
    else:
        op = make_algo_op(
            id=1, batch_id="B1", piece_id="P1", machine_id="M1", operator_id="O1",
            setup_hours=2.0, unit_hours=0.5,
        )
    scheduler = GreedyScheduler(FixedEfficiencyCalendar(), config_snapshot(auto_assign_enabled="no"))
    session = production_session(scheduler, operations=[op], batches={"B1": batch})
    decode_calls = MagicMock(wraps=session.native_preparation.operation_batch)
    monkeypatch.setattr(session.native_preparation, "operation_batch", decode_calls)
    decoded = decode_and_metrics(
        decode_session=session, objective_name="min_overdue", start_dt=datetime(2026, 10, 13, 8),
        dispatch_mode="sgs",
    )
    assert decoded.summary.scheduled_ops == 1 and decoded.summary.failed_ops == 0
    if source == "external":
        assert copied.call_count == 0
        assert decode_calls.call_count == 0
        assert session.native_preparation.piece_batches == {}
    else:
        assert copied.call_count == 1
        assert decode_calls.call_count >= 1
        assert decoded.results[0].end_time - decoded.results[0].start_time == timedelta(hours=5)
    assert batch.quantity == 20


def test_graph_node_projection_and_effort_use_scalar_piece_quantity_without_batch_copy(monkeypatch):
    from core.algorithm_runtime import operation_effort as effort_module
    from core.algorithm_runtime import piece_input
    from core.services.scheduler.graph import input_adapter

    copy_calls = MagicMock(wraps=copy)
    monkeypatch.setattr(piece_input, "copy", copy_calls)
    adapter_qty_calls = MagicMock(side_effect=operation_quantity)
    monkeypatch.setattr(input_adapter, "operation_quantity", adapter_qty_calls)
    effort_qty_calls = MagicMock(side_effect=operation_quantity)
    monkeypatch.setattr(effort_module, "operation_quantity", effort_qty_calls)

    batch = make_batch(batch_id="B1", quantity=20)
    ext_single = make_algo_op(
        id=1, batch_id="B1", piece_id="P1", op_code="EXT1", source="external",
        setup_hours=0.0, unit_hours=0.0, ext_days=2.0,
    )
    ext_merged = make_algo_op(
        id=2, batch_id="B1", piece_id="P1", op_code="EXT2", source="external",
        setup_hours=0.0, unit_hours=0.0, ext_merge_mode="merged", ext_group_id="G1", ext_group_total_days=3.0,
    )
    ext_nodes = input_adapter.build_operation_nodes_from_rows([ext_single, ext_merged], batches={"B1": batch})
    assert adapter_qty_calls.call_count == 0
    assert copy_calls.call_count == 0
    assert [node.duration_minutes for node in ext_nodes] == [2 * 24 * 60, 3 * 24 * 60]
    assert [node.piece_id for node in ext_nodes] == ["P1", "P1"]

    internal_piece = make_algo_op(
        id=3, batch_id="B1", piece_id="P1", source="internal", setup_hours=2.0, unit_hours=0.5,
    )
    internal_nodes = input_adapter.build_operation_nodes_from_rows([internal_piece], batches={"B1": batch})
    assert adapter_qty_calls.call_count == 1
    assert copy_calls.call_count == 0
    assert internal_nodes[0].duration_minutes == 150
    assert batch.quantity == 20

    int_effort = internal_operation_effort(internal_piece, batch)
    ext_effort = external_operation_effort(ext_merged, batch)
    assert effort_qty_calls.call_count == 2
    assert copy_calls.call_count == 0
    assert int_effort.target_quantity == 1 and int_effort.required_standard_hours == 2.5
    assert ext_effort.target_quantity == 1 and ext_effort.external_cycle_days == 3.0
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
    dependent = operation_dispatch_state(state, graph_state, make_algo_op(id=2))
    independent = operation_dispatch_state(state, graph_state, make_algo_op(id=3))
    assert dependent.prev_end("B1") == piece_end
    assert independent.prev_end("B1") == base
    assert state.prev_end("B1") == batch_end


def _external_op(*, merged, total_days=3.0, material_ready_date: Optional[datetime] = datetime(2026, 10, 16)):
    # 与排产输入构建一致：合并组只带整组周期，单道外协只带自己的周期。
    return make_algo_op(id=5, op_code="EXT", source="external", setup_hours=0.0, unit_hours=0.0,
                        material_ready_date=material_ready_date, ext_days=None if merged else 2.0,
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
    window = external_candidate_window(calendar, state.external_group_cache, op=op, prev_end=base)
    result, blocked = schedule_external(calendar=calendar, op=op, batch_progress={},
                                        external_group_cache={}, base_time=base, end_dt_exclusive=None)
    assert result is not None and not blocked and window == (result.start_time, result.end_time)
    assert window[0] == datetime(2026, 10, 16)
    if merged:
        # An already placed group block is shared as-is, even when it started before this member's material.
        placed = (base, base + timedelta(days=3))
        state.external_group_cache[external_group_key(op)] = placed
        assert external_candidate_window(calendar, state.external_group_cache, op=op, prev_end=base) == placed


def test_merged_external_group_is_cached_only_when_it_fits_the_window():
    from core.algorithm_runtime.piece_input import external_group_key
    from core.algorithms.greedy.external_groups import schedule_external

    base = datetime(2026, 10, 13, 8)
    op, calendar = _external_op(merged=True, total_days=5.0, material_ready_date=None), _NaturalDayCalendar()
    cache = {}
    result, blocked = schedule_external(calendar=calendar, op=op, batch_progress={}, external_group_cache=cache, base_time=base,
                                        end_dt_exclusive=base + timedelta(days=2))
    assert result is None and blocked is not None and blocked["code"] == "schedule_window_exceeded"
    assert cache == {}
    result, blocked = schedule_external(calendar=calendar, op=op, batch_progress={}, external_group_cache=cache, base_time=base,
                                        end_dt_exclusive=base + timedelta(days=10))
    assert result is not None and not blocked
    assert cache == {external_group_key(op): (result.start_time, result.end_time)}
