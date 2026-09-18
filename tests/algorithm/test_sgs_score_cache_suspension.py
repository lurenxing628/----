"""An instrumented scorer suspends every memo the cache hands out, so hooks observe each estimate."""

from types import SimpleNamespace
from unittest.mock import patch

from core.algorithm_runtime import internal_slot as internal_slot_module
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithms.greedy import auto_assign as auto_assign_module
from core.algorithms.greedy import scheduler as scheduler_module
from core.algorithms.greedy.dispatch import sgs as sgs_module
from core.algorithms.greedy.dispatch.sgs_score_cache import AutoAssignProbeContract, SgsScoreCache
from tests._support.sgs_slot_reuse_case import BASE, MemoryCalendar, make_case, make_scheduler


def _payload(rows, summary):
    fields = vars(summary).copy()
    fields.pop("duration_seconds")
    return [(r.op_id, r.machine_id, r.operator_id, r.start_time, r.end_time) for r in rows], fields


def _counted_decode(case, *, cache_enabled):
    """Instrument every estimator import the same way the large-resource-pool benchmark does."""
    original = internal_slot_module.estimate_internal_slot
    calls = []

    def observed(*args, **kwargs):
        calls.append(kwargs.get("machine_id"))
        return original(*args, **kwargs)

    attach = scheduler_module.attach_sgs_score_cache if cache_enabled else (lambda *args, **kw: None)
    with patch.object(internal_slot_module, "estimate_internal_slot", observed), \
            patch.object(auto_assign_module, "estimate_internal_slot", observed), \
            patch.object(sgs_module, "estimate_internal_slot", observed), \
            patch.object(scheduler_module, "attach_sgs_score_cache", attach):
        scheduler = make_scheduler()
        payload = _payload(*scheduler.schedule(**case)[:2])
    return payload, len(calls), scheduler._last_sgs_score_cache_stats


def test_hooked_estimator_sees_every_estimate_even_with_the_cache_attached():
    expected, plain_calls, _ = _counted_decode(make_case(12, 4, auto=True), cache_enabled=False)
    actual, hooked_calls, stats = _counted_decode(make_case(12, 4, auto=True), cache_enabled=True)
    assert actual == expected and hooked_calls == plain_calls > 0
    assert stats["hits"] == stats["pair_hits"] == stats["calendar_hits"] == stats["shared_slot_hits"] == 0


def test_suspended_round_serves_nothing_until_a_native_round_begins():
    state = ScheduleRunState(base_time=BASE)
    calendar = MemoryCalendar()
    cache = SgsScoreCache(state, auto_assign_enabled=True, native_auto_assign=True,
                          resource_pool={"machines_by_op_type": {}, "operators_by_machine": {}, "machines_by_operator": {},
                                         "pair_rank": {}},
                          probe=AutoAssignProbeContract(lambda *_: (("M1",), ("O1",)), lambda: True), calendar=calendar)
    op = SimpleNamespace(id=1, batch_id="B1", seq=1, source="internal", machine_id="M1", operator_id="O1",
                         setup_hours=1.0, unit_hours=0.0, op_type_name="T")
    assert cache.timing_calendar(calendar) is not calendar
    cache.suspend_round()
    assert cache.timing_calendar(calendar) is calendar
    assert cache.pair_estimate(op=op, machine_id="M1", operator_id="O1", prev_end=BASE, machine_timeline=state.machine_timeline,
                               operator_timeline=state.operator_timeline, compute=lambda: "estimate") is None
    computed = []
    assert cache.shared_slot_estimate(calendar=calendar, op=op, batch=SimpleNamespace(quantity=1, priority=None),
                                      machine_id="M1", operator_id="O1", prev_end=BASE, total_hours=1.0,
                                      end_dt_exclusive=None, machine_downtimes=(), compute=lambda: computed.append(1)) is None
    assert computed == [1]
    assert cache.selected_estimate({"op": op}) is None and cache.selected_resources(op) is None
    assert cache.begin_round()
    assert cache.timing_calendar(calendar) is not calendar
    assert cache.pair_estimate(op=op, machine_id="M1", operator_id="O1", prev_end=BASE, machine_timeline=state.machine_timeline,
                               operator_timeline=state.operator_timeline, compute=lambda: "estimate") == "estimate"
    assert cache.stats()["pair_misses"] == 1
    cache.forget(op)
    assert cache._pairs == {} and cache.stats()["pair_misses"] == 1
