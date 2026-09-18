"""Per-decode calendar timing memo and pair-estimate revalidation must be exact and provably scoped."""

from datetime import datetime, timedelta
from types import MethodType, SimpleNamespace
from unittest.mock import patch

import pytest

from core.algorithm_runtime import calendar_timing_memo as memo_module
from core.algorithm_runtime.calendar_timing_memo import MemoizedTimingCalendar, native_timing_calendar
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.internal_slot import estimate_internal_slot, refresh_changeover_penalty
from core.algorithm_runtime.resource_quality import MachineTypeState
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import sgs_handoff_scope
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch.sgs_score_cache import AutoAssignProbeContract, SgsScoreCache
from core.infrastructure.errors import ValidationError
from core.services.scheduler.calendar_engine import CalendarEngine
from core.services.scheduler.calendar_service import CalendarService
from core.services.scheduler.run.schedule_execution_reservations import ExecutionResourceCalendar
from tests._support.busy_block_case import BASE as SQLITE_BASE
from tests._support.busy_block_case import native_calendar, slot_case
from tests._support.sgs_slot_reuse_case import BASE, MemoryCalendar, make_case, make_scheduler


def _payload(rows, summary, strategy, params):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time, r.source) for r in rows], fields, str(strategy), params


def _run(kwargs, *, cache_enabled=True, scheduler_factory=make_scheduler):
    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = scheduler_factory()
        payload = _payload(*scheduler.schedule(**kwargs))
    return payload, scheduler._last_sgs_score_cache_stats


# ---------------------------------------------------------------------------
# Calendar timing guard and memo
# ---------------------------------------------------------------------------

def test_guard_accepts_native_engine_subclass_service_and_overlay_but_not_overrides():
    assert native_timing_calendar(MemoryCalendar())
    with native_calendar() as calendar:
        assert native_timing_calendar(calendar)
        # The execution overlay defines its timing surface explicitly and is certified over a native calendar.
        assert native_timing_calendar(ExecutionResourceCalendar(calendar, []))
        calendar.add_working_hours = MethodType(lambda self, *a, **k: None, calendar)
        assert not native_timing_calendar(calendar)
        assert not native_timing_calendar(ExecutionResourceCalendar(calendar, []))

    class Instrumented(MemoryCalendar):
        def adjust_to_working_time(self, dt, priority=None, machine_id=None, operator_id=None):
            return super().adjust_to_working_time(dt, priority=priority, machine_id=machine_id, operator_id=operator_id)

    class Certified(MemoryCalendar):
        def certified_slot_window(self, dt, *, priority=None, operator_id=None):
            return None

    class Forwarding(MemoryCalendar):
        def __getattr__(self, name):
            raise AttributeError(name)

    assert not native_timing_calendar(Instrumented())
    assert not native_timing_calendar(Certified())
    assert not native_timing_calendar(Forwarding())
    assert not native_timing_calendar(object())
    with patch.object(CalendarEngine, "get_efficiency", CalendarEngine.get_efficiency.__func__ if hasattr(CalendarEngine.get_efficiency, "__func__") else lambda *a, **k: 1.0):
        assert not native_timing_calendar(MemoryCalendar())
    with patch.object(CalendarService, "certified_slot_window", lambda *a, **k: None):
        with native_calendar() as calendar:
            assert not native_timing_calendar(calendar)


def test_memo_answers_repeats_once_and_never_memoizes_errors_or_exotic_arguments():
    calls = []

    class Counting(MemoryCalendar):
        def _resolve_calendar_row(self, date_str, op_id):
            calls.append(date_str)
            return super()._resolve_calendar_row(date_str, op_id)

    real = Counting()
    memo = MemoizedTimingCalendar(real)
    friday_evening = datetime(2026, 9, 11, 17)
    first = memo.adjust_to_working_time(friday_evening, priority="normal", operator_id="W01")
    assert first == real.adjust_to_working_time(friday_evening, priority="normal", operator_id="W01")
    assert memo.get_efficiency(BASE, operator_id="W03") == 0.85
    end = memo.add_working_hours(BASE, 2.5, priority=None, operator_id="W01")
    assert end == real.add_working_hours(BASE, 2.5, priority=None, operator_id="W01")
    assert memo.certified_slot_window(BASE, priority=None, operator_id="W01") is None
    with patch.object(CalendarEngine, "_policy_for_datetime", side_effect=AssertionError("memo must not call through")):
        assert memo.adjust_to_working_time(friday_evening, priority="normal", operator_id="W01") is first
        assert memo.get_efficiency(BASE, operator_id="W03") == 0.85
        assert memo.add_working_hours(BASE, 2.5, priority=None, operator_id="W01") is end
        assert memo.certified_slot_window(BASE, priority=None, operator_id="W01") is None
    assert (memo.hits, memo.misses) == (4, 4)

    for bad in (float("nan"), -1.0, True, None):
        with pytest.raises(ValidationError):
            memo.add_working_hours(BASE, bad, priority=None, operator_id="W01")
    assert memo._hours == {(BASE, 2.5, None, "W01"): end}

    class LoudDatetime(datetime):
        def date(self):
            calls.append("date")
            return super().date()

    exotic = LoudDatetime(2026, 9, 8, 8)
    for _ in range(2):
        memo.adjust_to_working_time(exotic, priority="normal", operator_id="W01")
        memo.adjust_to_working_time(BASE, priority=SimpleNamespace(), operator_id="W01")
    assert calls.count("date") == 2 and len(memo._adjust) == 1


def test_memo_is_bounded_and_certificate_is_the_underlying_one():
    with native_calendar() as calendar:
        memo = MemoizedTimingCalendar(calendar)
        window = memo.certified_slot_window(SQLITE_BASE + timedelta(hours=1), priority="normal", operator_id="O1")
        assert window == calendar.certified_slot_window(SQLITE_BASE + timedelta(hours=1), priority="normal", operator_id="O1")
        assert window == (SQLITE_BASE, SQLITE_BASE + timedelta(hours=8))
        with patch.object(memo_module, "_LIMIT", 3):
            for hour in range(5):
                memo.get_efficiency(SQLITE_BASE + timedelta(hours=hour), operator_id="O1")
            assert len(memo._efficiency) == 2


def test_estimator_uses_the_memo_only_inside_a_handoff_and_results_match():
    case = slot_case(machine=[(BASE, BASE + timedelta(hours=1)), (BASE + timedelta(hours=1), BASE + timedelta(hours=3))])
    case["base_time"] = case["prev_end"] = BASE
    calendar = MemoryCalendar()
    plain = estimate_internal_slot(calendar=calendar, **case)
    cache = _cache(calendar)
    with sgs_handoff_scope(cache):
        first = estimate_internal_slot(calendar=calendar, **case)
        second = estimate_internal_slot(calendar=calendar, **case)
    assert first == second == plain
    stats = cache.stats()
    assert stats["calendar_misses"] > 0 and stats["calendar_hits"] >= stats["calendar_misses"]
    # The span starts at the first adjusted attempt, not at the slot the walk finally reached.
    assert cache._last_scan == (BASE, plain.end_time) and plain.start_time == BASE + timedelta(hours=3)


def _cache(calendar, **overrides):
    state = ScheduleRunState(base_time=BASE)
    probe = AutoAssignProbeContract(lambda op, pool: (("M1",), ("W01",)), lambda: True)
    pool = {"machines_by_op_type": {"T": ["M1"]}, "operators_by_machine": {"M1": ["W01"]}, "machines_by_operator": {}, "pair_rank": {}}
    kwargs = dict(auto_assign_enabled=True, resource_pool=pool, native_auto_assign=True, probe=probe, calendar=calendar)
    kwargs.update(overrides)
    return SgsScoreCache(state, **kwargs)


# ---------------------------------------------------------------------------
# Pair-estimate revalidation
# ---------------------------------------------------------------------------

def _op(**overrides):
    fields = dict(id=7, op_code="OP7", batch_id="B1", seq=1, source="internal", machine_id="", operator_id="",
                  op_type_id="T", op_type_name="TURN", setup_hours=1.0, unit_hours=0.0)
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _pair_inputs(cache, op):
    state = cache.state
    return dict(op=op, machine_id="M1", operator_id="W01", prev_end=BASE,
                machine_timeline=state.machine_timeline, operator_timeline=state.operator_timeline)


def _compute(cache, op, calendar):
    state = cache.state
    batch = SimpleNamespace(batch_id="B1", quantity=1, priority="normal", due_date=None)

    def compute():
        return estimate_internal_slot(
            calendar=calendar, op=op, batch=batch, machine_id="M1", operator_id="W01", base_time=BASE, prev_end=BASE,
            machine_timeline=state.machine_timeline.get("M1") or [], operator_timeline=state.operator_timeline.get("W01") or [],
            end_dt_exclusive=None, machine_downtimes=[], last_op_type_by_machine=state.last_op_type_by_machine, abort_after=None,
        )

    return compute


def _occupy(cache, resource_kind, resource_id, start, end):
    timeline = cache.state.machine_timeline if resource_kind == "machine" else cache.state.operator_timeline
    occupy_resource(timeline, resource_id, start, end)


@pytest.mark.parametrize("resource_kind", ["machine", "operator"])
def test_blocks_outside_the_scan_span_keep_the_estimate_blocks_inside_force_a_new_scan(resource_kind):
    calendar = MemoryCalendar()
    cache = _cache(calendar)
    op = _op()
    resource_id = "M1" if resource_kind == "machine" else "W01"
    with sgs_handoff_scope(cache):
        _occupy(cache, resource_kind, resource_id, BASE, BASE + timedelta(hours=2))
        compute = _compute(cache, op, calendar)
        first = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert (first.start_time, first.end_time) == (BASE + timedelta(hours=2), BASE + timedelta(hours=3))
        # Later on the same day, after the estimated slot: the walk never looked there.
        _occupy(cache, resource_kind, resource_id, BASE + timedelta(hours=5), BASE + timedelta(hours=6))
        again = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert again is first and cache.stats()["pair_revalidated"] == 1
        assert again == compute()
        # Touching the scan end from the right still counts as inside: the skip could have extended through it.
        _occupy(cache, resource_kind, resource_id, BASE + timedelta(hours=3), BASE + timedelta(hours=4))
        third = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert third is not first and third == compute() and cache.stats()["pair_misses"] == 2
        # Beyond the new span [10:00, 11:00]: revalidated again without a scan.
        _occupy(cache, resource_kind, resource_id, BASE + timedelta(hours=4, minutes=30), BASE + timedelta(hours=4, minutes=45))
        assert cache.pair_estimate(**_pair_inputs(cache, op), compute=compute) is third
        assert cache.stats()["pair_revalidated"] == 2
        # A block inside the slot moves the estimate; the fresh scan is what the memo returns.
        _occupy(cache, resource_kind, resource_id, BASE + timedelta(hours=2, minutes=30), BASE + timedelta(hours=2, minutes=45))
        fourth = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        # 10:00 -> 10:45 -> 12:00 -> 12:45 -> 14:00: every later block is hopped over on the fresh scan.
        assert fourth == compute() and fourth.start_time == BASE + timedelta(hours=6)
        assert cache.stats()["pair_misses"] == 3


def test_unlogged_timeline_mutation_disables_revalidation():
    calendar = MemoryCalendar()
    cache = _cache(calendar)
    op = _op()
    with sgs_handoff_scope(cache):
        compute = _compute(cache, op, calendar)
        first = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        # Mutating the list directly bypasses occupy_resource: the growth is unaccounted for.
        cache.state.machine_timeline.setdefault("M1", []).append((BASE + timedelta(days=3), BASE + timedelta(days=3, hours=1)))
        second = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert second == first and second is not first
        assert cache.stats()["pair_revalidated"] == 0 and cache.stats()["pair_misses"] == 2
        # Replacing the list wholesale is not a growth either.
        cache.state.machine_timeline["M1"] = list(cache.state.machine_timeline["M1"])
        cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert cache.stats()["pair_misses"] == 3


def test_changed_predecessor_end_or_missing_scan_span_requires_a_new_scan():
    calendar = MemoryCalendar()
    cache = _cache(calendar)
    op = _op()
    with sgs_handoff_scope(cache):
        compute = _compute(cache, op, calendar)
        cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        _occupy(cache, "machine", "M1", BASE + timedelta(days=2), BASE + timedelta(days=2, hours=1))
        inputs = dict(_pair_inputs(cache, op), prev_end=BASE + timedelta(hours=1))
        cache.pair_estimate(**inputs, compute=compute)
        assert cache.stats()["pair_revalidated"] == 0 and cache.stats()["pair_misses"] == 2
        entry = cache._pairs[id(op)][("M1", "W01")]
        entry.scan = None
        _occupy(cache, "machine", "M1", BASE + timedelta(days=3), BASE + timedelta(days=3, hours=1))
        cache.pair_estimate(**inputs, compute=compute)
        assert cache.stats()["pair_revalidated"] == 0 and cache.stats()["pair_misses"] == 3


def test_changeover_penalty_is_refreshed_from_the_current_type_history():
    calendar = MemoryCalendar()
    cache = _cache(calendar)
    types: MachineTypeState = cache.state.last_op_type_by_machine
    op = _op(op_type_name="TURN")
    with sgs_handoff_scope(cache):
        compute = _compute(cache, op, calendar)
        first = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert first.changeover_penalty == 0
        # A MILL operation recorded well after the estimated slot changes the tail type but not the slot.
        types["M1"] = "MILL"
        types.record("M1", BASE + timedelta(days=5), BASE + timedelta(days=5, hours=1), 99, "MILL")
        _occupy(cache, "machine", "M1", BASE + timedelta(days=5), BASE + timedelta(days=5, hours=1))
        second = cache.pair_estimate(**_pair_inputs(cache, op), compute=compute)
        assert cache.stats()["pair_revalidated"] == 1
        assert second == compute()
        assert second.changeover_penalty == compute().changeover_penalty
        assert refresh_changeover_penalty(first, op=op, machine_id="M1", last_op_type_by_machine=types) == second


def test_decode_reports_revalidations_and_calendar_hits_while_matching_full_rescoring():
    expected, _ = _run(make_case(30, 6, auto=True), cache_enabled=False)
    actual, stats = _run(make_case(30, 6, auto=True), cache_enabled=True)
    assert actual == expected
    assert stats["pair_revalidated"] > 0
    assert stats["calendar_hits"] > stats["calendar_misses"] > 0


def test_instrumented_calendar_inside_a_decode_gets_every_call_and_the_same_plan():
    class Counting(MemoryCalendar):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def add_working_hours(self, start, hours, priority=None, machine_id=None, operator_id=None):
            self.calls += 1
            return super().add_working_hours(start, hours, priority=priority, machine_id=machine_id, operator_id=operator_id)

    holder = {}

    def counting_scheduler():
        holder["calendar"] = Counting()
        return scheduler_module.GreedyScheduler(holder["calendar"], {"auto_assign_enabled": "yes"})

    expected, _ = _run(make_case(12, 4, auto=True), cache_enabled=False)
    actual, stats = _run(make_case(12, 4, auto=True), cache_enabled=True, scheduler_factory=counting_scheduler)
    assert actual == expected
    assert stats["calendar_hits"] == stats["calendar_misses"] == 0
    assert holder["calendar"].calls > 0
