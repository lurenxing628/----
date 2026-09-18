"""Shared slots chain same-efficiency work windows across days, so saturated resources still share exactly."""

from types import SimpleNamespace
from unittest.mock import patch

from core.algorithm_runtime import internal_slot
from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import sgs_handoff_scope
from core.algorithm_runtime.sgs_shared_slot import constant_efficiency_span
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_score_cache import AutoAssignProbeContract, SgsScoreCache
from tests._support.busy_block_case import BASE, at, day_row, native_calendar, spans


def _cache(calendar, occupied=()):
    state = ScheduleRunState(base_time=BASE)
    state.machine_timeline["M1"] = list(occupied)
    state.operator_timeline["O1"] = []
    state.last_op_type_by_machine["M1"] = "MILL"
    return SgsScoreCache(state, auto_assign_enabled=False, native_auto_assign=True, resource_pool=None,
                         probe=AutoAssignProbeContract(lambda *_: None, lambda: True), calendar=calendar)


def _evaluate(cache, calendar, *, release=BASE, hours=1.0, op_id=1, op_type="TURN", calls=None, shared=True):
    op = SimpleNamespace(id=op_id, op_type_name=op_type, setup_hours=hours, unit_hours=0.0)
    batch = SimpleNamespace(quantity=1, priority="normal")
    state = cache.state

    def compute():
        if calls is not None:
            calls.append(op_id)
        return internal_slot.estimate_internal_slot(
            calendar=calendar, op=op, batch=batch, machine_id="M1", operator_id="O1", base_time=BASE,
            prev_end=release, total_hours_base=hours, machine_timeline=state.machine_timeline["M1"],
            operator_timeline=state.operator_timeline["O1"], machine_downtimes=(),
            last_op_type_by_machine=state.last_op_type_by_machine, abort_after=None, end_dt_exclusive=None)

    with sgs_handoff_scope(cache):
        if not shared:
            return compute()
        return cache.shared_slot_estimate(
            calendar=calendar, op=op, batch=batch, machine_id="M1", operator_id="O1", prev_end=release,
            total_hours=hours, end_dt_exclusive=None, machine_downtimes=(), compute=compute)


def test_slot_landing_on_a_later_day_is_shared_when_efficiency_is_constant():
    with native_calendar() as calendar:
        cache, calls = _cache(calendar, spans((0, 8))), []
        first = _evaluate(cache, calendar, hours=2.0, calls=calls)
        assert first.start_time == at(24) and first.end_time == at(26)
        later = _evaluate(cache, calendar, release=at(3), op_id=2, op_type="MILL", hours=2.0, calls=calls)
        assert calls == [1] and cache.stats()["shared_slot_hits"] == 1
        assert (later.start_time, later.end_time) == (first.start_time, first.end_time)
        assert later == _evaluate(cache, calendar, release=at(3), op_id=2, op_type="MILL", hours=2.0, shared=False)
        assert first.changeover_penalty == 1 and later.changeover_penalty == 0


def test_slot_spanning_an_efficiency_change_is_never_shared():
    with native_calendar(rows=[day_row(1, efficiency=0.5)]) as calendar:
        cache, calls = _cache(calendar, spans((0, 8))), []
        _evaluate(cache, calendar, hours=2.0, calls=calls)
        later = _evaluate(cache, calendar, release=at(3), op_id=2, hours=2.0, calls=calls)
        assert calls == [1, 2] and cache.stats()["shared_slot_hits"] == 0
        assert later == _evaluate(cache, calendar, release=at(3), op_id=2, hours=2.0, shared=False)


def test_constant_efficiency_span_chains_windows_and_stops_at_changes_or_midnight():
    with native_calendar(rows=[day_row(3, efficiency=1.25), day_row(5, shift_start="20:00", shift_end="04:00")]) as calendar:
        memo = MemoizedTimingCalendar(calendar)
        assert constant_efficiency_span(memo, at(0), at(6), None, "O1")
        assert constant_efficiency_span(memo, at(6), at(24 + 2), None, "O1")
        assert constant_efficiency_span(memo, at(6), at(48 + 7), None, "O1")
        assert not constant_efficiency_span(memo, at(6), at(72 + 1), None, "O1")
        assert constant_efficiency_span(memo, at(72), at(72 + 7), None, "O1")
        # A night shift certifies only its pre-midnight part: the chain reaches it but ends at midnight.
        assert constant_efficiency_span(memo, at(96), at(120 + 13), None, "O1")
        assert not constant_efficiency_span(memo, at(96), at(120 + 17), None, "O1")
        assert constant_efficiency_span(memo, at(120 + 12), at(120 + 13), None, "O1")
        assert not constant_efficiency_span(memo, at(120 + 12), at(120 + 17), None, "O1")


def _saturated_case(count):
    batches, operations = {}, []
    for index in range(count):
        bid = f"B{index:03d}"
        batches[bid] = SimpleNamespace(batch_id=bid, priority="normal", due_date=None, ready_status="yes",
                                       ready_date=None, created_at=None, quantity=1)
        operations.append(SimpleNamespace(id=index + 1, op_code=bid, batch_id=bid, seq=1, source="internal",
                                          machine_id="M1", operator_id="O1", setup_hours=1.0, unit_hours=0.0,
                                          op_type_id="T", op_type_name="TURN"))
    return dict(operations=operations, batches=batches, start_dt=BASE, dispatch_mode="sgs", dispatch_rule="slack")


def _decode(case, *, cache_enabled):
    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with native_calendar() as calendar, patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = scheduler_module.GreedyScheduler(calendar_service=calendar)
        rows, summary, _strategy, _params = scheduler.schedule(**case)
    return [(r.op_id, r.start_time, r.end_time) for r in rows], summary.failed_ops, scheduler._last_sgs_score_cache_stats


def test_saturated_single_resource_shares_nearly_every_candidate_and_matches_full_scoring():
    count = 48
    expected, failed, off = _decode(_saturated_case(count), cache_enabled=False)
    actual, _failed, on = _decode(_saturated_case(count), cache_enabled=True)
    assert actual == expected and failed == 0 and len(actual) == count
    assert not any(off.values())
    # Round k scores count-k identical slot requests: one native walk, the rest shared.
    assert on["shared_slot_hits"] >= count * (count - 1) // 2 - count
    assert on["shared_slot_misses"] <= 2 * count
    assert max(end for _op, _start, end in actual).date() > BASE.date()
