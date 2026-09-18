"""The execution release-floor overlay is a certifiable timing calendar: every decode memo stays on and exact."""

from datetime import timedelta
from types import MethodType, SimpleNamespace
from unittest.mock import patch

from core.algorithm_runtime.calendar_timing_memo import native_timing_calendar
from core.algorithms.greedy import scheduler as scheduler_module
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import (
    ExecutionResourceCalendar,
    ExecutionResourceReservation,
    native_execution_overlay_timing,
    reserve_execution_machines,
)
from tests._support.busy_block_case import BASE, at, native_calendar, run_estimate, slot_case, spans


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
        bad_floor = ExecutionResourceCalendar(calendar, [])
        bad_floor._release_by_operator["O1"] = "2026-09-08"
        assert not native_timing_calendar(bad_floor)
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
        batches[bid] = SimpleNamespace(batch_id=bid, priority="urgent" if b % 4 == 0 else "normal",
                                       due_date=(BASE + timedelta(days=2 + b % 9)).date(), ready_status="yes",
                                       ready_date=None, created_at=None, quantity=1 + b % 3)
        for seq in range(ops_per_batch):
            oid = b * ops_per_batch + seq + 1
            operations.append(SimpleNamespace(
                id=oid, op_code=f"{bid}_{seq}", batch_id=bid, seq=seq, source="internal",
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
        scheduler = scheduler_module.GreedyScheduler(calendar_service=calendar, config_service={"auto_assign_enabled": "no"})
        rows, summary, _strategy, _params = scheduler.schedule(**case)
    return _payload(rows, summary), scheduler._last_sgs_score_cache_stats


def _single_resource_case(count=40):
    batches, operations = {}, []
    for index in range(count):
        bid = f"B{index:03d}"
        batches[bid] = SimpleNamespace(batch_id=bid, priority="normal", due_date=None, ready_status="yes",
                                       ready_date=None, created_at=None, quantity=1)
        operations.append(SimpleNamespace(id=index + 1, op_code=bid, batch_id=bid, seq=1, source="internal",
                                          machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0,
                                          op_type_id="T", op_type_name="TURN"))
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


def test_saturated_decode_with_release_floor_matches_cache_off_with_shared_slots_on():
    reservations = [_reservation("O1", "M9", -1.0, 2.5)]
    (expected, off), (actual, on) = [
        _decode_with_floors(_single_resource_case(), reservations, cache_enabled=enabled) for enabled in (False, True)]
    assert actual == expected and actual[1]["failed_ops"] == 0
    assert min(start for _op, _m, _operator, start, _end in actual[0]) == at(2.5)
    assert not any(off.values())
    assert on["calendar_hits"] > 0 and on["shared_slot_hits"] >= 40 * 39 // 2 - 40
