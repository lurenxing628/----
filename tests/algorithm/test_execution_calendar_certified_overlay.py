"""The execution release-floor overlay is a certifiable timing calendar: every decode memo stays on and exact."""

from datetime import timedelta
from types import MethodType, SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithm_contracts.types import OpForScheduleAlgo
from core.algorithm_runtime.calendar_timing_memo import native_timing_calendar
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_graph import graph_priority_key_map
from core.algorithms.greedy.dispatch.sgs_priority_frontier import make_priority_queue
from core.algorithms.greedy.dispatch.sgs_priority_pruning import GraphPriorityPruning
from core.errors import ValidationError
from core.services.scheduler.calendar.service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    ExecutionResourceReservation,
    native_execution_overlay_timing,
    reserve_execution_machines,
)
from tests._support.algo_operations import make_algo_op, make_batch
from tests._support.busy_block_case import BASE, at, native_calendar, run_estimate, slot_case, spans
from tests._support.schedule_decode import config_snapshot, production_decode_in_session


def _reservation(operator_id="O1", machine_id="M2", start=0.0, end=0.5):
    return ExecutionResourceReservation(99, machine_id, operator_id, at(start), at(end))


def test_guard_certifies_overlay_only_over_a_certified_calendar_with_intact_methods():
    with native_calendar() as calendar:
        overlay = ExecutionResourceCalendar(calendar, [_reservation()])
        assert native_timing_calendar(overlay) and native_execution_overlay_timing(overlay)

        class Sub(ExecutionResourceCalendar):
            pass

        assert not native_timing_calendar(Sub(calendar, []))
        shadowed = ExecutionResourceCalendar(calendar, [])
        shadowed.adjust_to_working_time = MethodType(lambda self, dt, **kw: dt, shadowed)
        assert not native_timing_calendar(shadowed)
        with patch.object(ExecutionResourceCalendar, "get_efficiency", lambda self, dt, **kw: 1.0):
            assert not native_timing_calendar(overlay)
        assert native_timing_calendar(overlay)
        calendar.add_working_hours = MethodType(lambda self, *a, **k: None, calendar)
        assert not native_timing_calendar(overlay)
    stub = SimpleNamespace(adjust_to_working_time=lambda dt, **kw: dt, add_working_hours=lambda s, h, **kw: s,
                           get_efficiency=lambda dt, **kw: 1.0)
    assert not native_timing_calendar(ExecutionResourceCalendar(stub, []))


def test_certificate_is_absent_below_the_release_floor_and_clamped_at_or_after_it():
    with native_calendar() as calendar:
        overlay = ExecutionResourceCalendar(calendar, [_reservation(start=0.0, end=0.5)])
        assert overlay.certified_slot_window(at(0.25), operator_id="O1") is None
        assert overlay.certified_slot_window(at(0.5), operator_id="O1") == (at(0.5), at(8))
        assert overlay.certified_slot_window(at(2), operator_id="O1") == (at(0.5), at(8))
        assert overlay.certified_slot_window(at(0.25), operator_id="O2") == calendar.certified_slot_window(at(0.25), operator_id="O2")
        assert overlay.certified_slot_window(at(9), operator_id="O1") is None
        assert overlay.adjust_to_working_time(at(0.25), operator_id="O1") == at(0.5)
        assert overlay.adjust_to_working_time(at(0.25), operator_id="O2") == at(0.25)
        assert overlay.add_working_hours(at(7), 2.0, operator_id="O1") == calendar.add_working_hours(at(7), 2.0, operator_id="O1")
        assert overlay.get_efficiency(at(1), operator_id="O1") == calendar.get_efficiency(at(1), operator_id="O1")
        assert overlay.add_calendar_days(at(1), 2.0) == at(49)


def test_release_floor_lookup_keeps_the_exact_operator_identity():
    with native_calendar() as calendar:
        overlay = ExecutionResourceCalendar(calendar, [_reservation(start=0.0, end=0.5)])
        # 读取与写入同一口径：带空格的编号是另一个身份，不借用 "O1" 的释放下限。
        assert overlay.adjust_to_working_time(at(0.25), operator_id=" O1 ") == at(0.25)
        assert overlay.certified_slot_window(at(0.25), operator_id=" O1 ") == calendar.certified_slot_window(
            at(0.25), operator_id=" O1 ")
        assert overlay.adjust_to_working_time(at(0.25), operator_id="O1") == at(0.5)


def test_busy_block_closure_engages_through_the_overlay_certificate():
    outputs = []
    for legacy in (True, False):
        with native_calendar() as native:
            overlay = ExecutionResourceCalendar(native, [_reservation(start=0.0, end=0.5)])
            outputs.append(run_estimate(overlay, slot_case(machine=spans((0.5, 1), (1, 2), (2, 3))), legacy=legacy))
    (expected, legacy_count), (actual, closure_count) = outputs
    assert actual == expected and actual.start_time == at(3)
    assert closure_count < legacy_count == 4


def _saturated_case(batch_count=30, ops_per_batch=3):
    machines, operators = ["M1", "M2", "M3"], ["O1", "O2"]
    batches, operations, predecessors, successors = {}, [], {}, {}
    for b in range(batch_count):
        bid = f"B{b:03d}"
        batches[bid] = make_batch(batch_id=bid, priority="urgent" if b % 4 == 0 else "normal",
                                  due_date=(BASE + timedelta(days=2 + b % 9)).date(), quantity=1 + b % 3)
        for seq in range(ops_per_batch):
            oid = b * ops_per_batch + seq + 1
            operations.append(make_algo_op(
                id=oid, op_code=f"{bid}_{seq}", batch_id=bid, seq=seq,
                machine_id=machines[(b + seq) % 3], operator_id=operators[(b + 2 * seq) % 2],
                setup_hours=0.25 * (1 + oid % 3), unit_hours=0.2 + 0.1 * (oid % 4),
                op_type_id=f"T{oid % 2}", op_type_name=f"TYPE{oid % 2}"))
            predecessors[oid] = [oid - 1] if seq else []
            successors[oid] = [oid + 1] if seq + 1 < ops_per_batch else []
    context = {
        "enabled": True, "schedulable_op_ids": list(predecessors), "fixed_op_ids": [], "score_enabled": True,
        "predecessor_op_ids_by_op_id": predecessors, "successor_op_ids_by_op_id": successors,
        "sort_key_by_op_id": {op.id: ((op.id - 1) // ops_per_batch, op.seq, op.id) for op in operations},
        "graph_priority_key_by_op_id": {op.id: (float((op.id * 7) % 11), float(op.id)) for op in operations},
    }
    return dict(operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="atc",
                graph_ready_context=context)


def _payload(rows, summary):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time) for r in rows], fields


def _decode(calendar, case, *, cache_enabled):
    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = scheduler_module.GreedyScheduler(calendar_service=calendar,
                                                     config_service=config_snapshot(auto_assign_enabled="no"))
        session, decoded = production_decode_in_session(scheduler, **case)
    # The decode's own run context keeps the score cache it attached (None when the cache is off).
    cache = session.native_preparation.run_context.sgs_score_cache
    return _payload(decoded.results, decoded.summary), (cache.stats() if cache is not None else {})


def _single_resource_case(count=40):
    batches, operations = {}, []
    for index in range(count):
        bid = f"B{index:03d}"
        batches[bid] = make_batch(batch_id=bid)
        operations.append(make_algo_op(id=index + 1, op_code=bid, batch_id=bid, machine_id="M1", operator_id="O1",
                                       setup_hours=1.0, unit_hours=0.0, op_type_id="T", op_type_name="TURN"))
    return dict(operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")


def _decode_with_floors(case, reservations, *, cache_enabled):
    with native_calendar() as native:
        case = dict(case, machine_downtimes=reserve_execution_machines({}, reservations))
        overlay = ExecutionResourceCalendar(native, reservations)
        assert isinstance(native, CalendarService) and native_timing_calendar(overlay)
        return _decode(overlay, case, cache_enabled=cache_enabled)


def test_graph_decode_with_release_floors_matches_cache_off_with_memo_and_pruning_on():
    reservations = [_reservation("O1", "M1", -2.0, 3.0), _reservation("O2", "M2", -1.0, 1.5)]
    (expected, off), (actual, on) = [
        _decode_with_floors(_saturated_case(), reservations, cache_enabled=enabled) for enabled in (False, True)]
    assert actual == expected
    assert actual[1]["failed_ops"] == 0 and actual[1]["scheduled_ops"] == 90
    assert all(start >= at(3) for _op, _m, operator, start, _end in actual[0] if operator == "O1")
    assert all(start >= at(1.5) for _op, _m, operator, start, _end in actual[0] if operator == "O2")
    assert not any(off.values())
    assert on["calendar_hits"] > 0 and on["graph_candidates_pruned"] > 0


def _mixed_case(batch_count=30):
    case = _saturated_case(batch_count=batch_count)
    for index, op in enumerate(case["operations"]):
        batch_index, seq = divmod(index, 3)
        if seq == 1 or (seq == 2 and batch_index % 3 == 0):
            op.source, op.machine_id, op.operator_id = "external", None, None
            op.ext_days = 0.25
            if batch_index % 3 == 0:
                # 与排产输入构建一致：合并组只带整组周期（规范浮点数），不带单道周期。
                op.ext_merge_mode, op.ext_group_id, op.ext_days = "merged", "supplier-group", None
                op.ext_group_total_days = 0.5
    return case


def test_mixed_external_decode_keeps_pruning_and_exact_schedule_with_release_floors():
    reservations = [_reservation("O1", "M1", -2.0, 3.0)]
    (expected, off), (actual, on) = [
        _decode_with_floors(_mixed_case(), reservations, cache_enabled=enabled) for enabled in (False, True)]
    assert actual == expected
    assert actual[1]["failed_ops"] == 0 and actual[1]["scheduled_ops"] == 90
    assert not any(off.values())
    assert on["graph_candidates_pruned"] > 0


def _pruning(case, calendar):
    graph = dict(case["graph_ready_context"])
    graph["op_by_id"] = {op.id: (op.batch_id, op) for op in case["operations"]}
    graph["ready_op_ids"] = {op.id for op in case["operations"] if op.seq == 0}
    hours = {op.id: float(op.setup_hours + op.unit_hours * case["batches"][op.batch_id].quantity)
             for op in case["operations"] if op.source == "internal"}
    return GraphPriorityPruning(graph, case["batches"], hours, strict_mode=True, calendar=calendar), graph


@pytest.mark.parametrize("admitted", [False, True])
def test_priority_pruning_reuses_admission_and_preserves_raw_key_checks(admitted):
    case = _saturated_case(batch_count=4, ops_per_batch=1)
    keys = {op.id: (float((op.id - 1) // 2), 0.0) for op in case["operations"]}
    if admitted:
        keys = graph_priority_key_map(keys, schedulable_ids=set(keys))
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = keys
    checks, original = [], GraphPriorityPruning._key_valid

    def check(pruning, key):
        checks.append(key)
        return original(pruning, key)

    with native_calendar() as calendar, patch.object(GraphPriorityPruning, "_key_valid", check):
        pruning, graph = _pruning(case, calendar)
        candidates = list(graph["op_by_id"].values())
        assert pruning.supported
        assert [[op.id for _batch, op in pruning.frontier(candidates[index:], graph)]
                for index in (0, 1)] == [[1, 2], [2]]
        assert len(checks) == (0 if admitted else 4 + 4 + 3)
        first_key = keys.pop(1)
        assert pruning.frontier(candidates, graph) is None
        keys[1] = first_key
        graph["graph_priority_key_by_op_id"] = dict(keys)
        graph["graph_priority_key_by_op_id"][1] = (float("nan"), 0.0)
        assert pruning.frontier(candidates, graph) is None


def test_priority_pruning_requires_uniform_admitted_key_width():
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = graph_priority_key_map(
        {1: (0.0,), 2: (1.0, 0.0)}, schedulable_ids={1, 2},
    )
    with native_calendar() as calendar:
        pruning, _graph = _pruning(case, calendar)
    assert not pruning.supported


@pytest.mark.parametrize("invalid", [float("nan"), float("inf")])
def test_priority_key_admission_keeps_nonfinite_input_error(invalid):
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    case["graph_ready_context"]["graph_priority_key_by_op_id"][1] = (invalid, 0.0)
    with native_calendar() as calendar, pytest.raises(ValidationError) as exc:
        _decode(calendar, case, cache_enabled=True)
    assert exc.value.field == "graph_ready_context"
    assert exc.value.message == "图评分 key 不能包含 NaN 或 Inf。"


def test_external_calendar_override_disables_both_narrowing_paths_without_disabling_internal_timing():
    with native_calendar() as calendar:
        pruning, graph = _pruning(_mixed_case(batch_count=50), calendar)
        internal, _ = _pruning(_saturated_case(batch_count=50), calendar)
        queue = make_priority_queue(graph, pruning)
        assert pruning.supported and not pruning.fixed_resources and queue is not None
        calendar.add_calendar_days = MethodType(lambda self, start, days: start + timedelta(days=days), calendar)
        assert native_timing_calendar(calendar) and not native_timing_calendar(calendar, include_calendar_days=True)
        assert internal.intact() and internal.fixed_resources
        assert queue.head(set()) is None and not pruning.supported
        assert pruning.frontier(list(graph["op_by_id"].values()), graph) is None


@pytest.mark.parametrize("merged", [False, True])
def test_out_of_range_external_duration_keeps_the_complete_path_and_the_calendar_error(merged):
    # 输入构建只保证周期是正有限数；超出日历可加天数的周期由日历拒绝，剪枝认证不能放行。
    case = _saturated_case(batch_count=3, ops_per_batch=1)
    first = case["operations"][0]
    first.source = "external"
    if merged:
        first.ext_merge_mode, first.ext_group_id, first.ext_group_total_days = "merged", "G", 36501.0
    else:
        first.ext_days = 36501.0
    errors = []
    for enabled in (False, True):
        with native_calendar() as calendar:
            pruning, _ = _pruning(case, calendar)
            assert not pruning.supported
            with pytest.raises(ValidationError) as exc:
                _decode(calendar, case, cache_enabled=enabled)
            errors.append((exc.value.field, str(exc.value)))
    assert errors[0] == errors[1]
    assert errors[0][0] == "days"


def test_external_duration_descriptor_is_not_read_by_certification():
    calls = []

    class External(OpForScheduleAlgo):
        @property
        def ext_days(self):
            calls.append("duration")
            return 0.25

        @ext_days.setter
        def ext_days(self, value):
            pass  # 构造时的赋值不落实例字典，读取只走上面的描述符

    case = _saturated_case(batch_count=2, ops_per_batch=1)
    first = case["operations"][0]
    case["operations"][0] = External(**dict(vars(first), source="external"))
    with native_calendar() as calendar:
        pruning, _ = _pruning(case, calendar)
    assert not pruning.supported and calls == []


def test_blocked_lowest_external_group_still_scores_the_other_ready_operations():
    case = _saturated_case(batch_count=2, ops_per_batch=1)
    external, internal = case["operations"]
    external.source, external.ext_days = "external", 2.0
    case["end_date"] = BASE.date()
    case["graph_ready_context"]["graph_priority_key_by_op_id"] = {external.id: (0.0, 0.0), internal.id: (1.0, 0.0)}
    outputs = []
    for enabled in (False, True):
        with native_calendar() as calendar:
            payload, _ = _decode(calendar, case, cache_enabled=enabled)
            outputs.append(payload)
    assert outputs[0] == outputs[1]
    assert [row[0] for row in outputs[1][0]] == [internal.id]
    assert outputs[1][1]["failed_ops"] == 1


def test_external_overlay_keeps_two_argument_calendar_protocol():
    calendar = SimpleNamespace(add_calendar_days=lambda start, days: start + timedelta(days=days))
    overlay = ExecutionResourceCalendar(calendar, [])
    assert overlay.add_calendar_days(BASE, 0.5) == at(12)
    assert not native_timing_calendar(overlay, include_calendar_days=True)


def test_saturated_decode_with_release_floor_matches_cache_off_with_shared_slots_on():
    reservations = [_reservation("O1", "M9", -1.0, 2.5)]
    (expected, off), (actual, on) = [
        _decode_with_floors(_single_resource_case(), reservations, cache_enabled=enabled) for enabled in (False, True)]
    assert actual == expected and actual[1]["failed_ops"] == 0
    assert min(start for _op, _m, _operator, start, _end in actual[0]) == at(2.5)
    assert not any(off.values())
    assert on["calendar_hits"] > 0 and on["shared_slot_hits"] >= 40 * 39 // 2 - 40
