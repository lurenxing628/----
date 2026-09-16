"""Cross-operation slot reuse must preserve the actual native earliest-slot result."""

import random
from types import SimpleNamespace

import pytest

from core.algorithm_runtime import internal_slot
from core.algorithm_runtime.downtime import occupy_resource
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.sgs_estimate_reuse import sgs_handoff_scope
from core.algorithms.greedy.dispatch.sgs_score_cache import AutoAssignProbeContract, SgsScoreCache
from tests._support.busy_block_case import BASE, at, day_row, native_calendar, spans


def _cache(calendar, occupied=()):
    state = ScheduleRunState(base_time=BASE)
    state.machine_timeline["M1"] = list(occupied)
    state.operator_timeline["O1"] = []
    state.last_op_type_by_machine["M1"] = "MILL"
    cache = SgsScoreCache(state, auto_assign_enabled=False, native_auto_assign=True, resource_pool=None,
                         probe=AutoAssignProbeContract(lambda *_: None, lambda: True), calendar=calendar)
    return cache


def _evaluate(cache, calendar, *, release=BASE, hours=1.0, op_id=1, op_type="TURN", priority="normal",
              cutoff=None, downtime=(), calls=None, shared=True):
    op = SimpleNamespace(id=op_id, op_type_name=op_type, setup_hours=hours, unit_hours=0.0)
    batch = SimpleNamespace(quantity=1, priority=priority)
    state = cache.state

    def compute():
        if calls is not None:
            calls.append(op_id)
        return internal_slot.estimate_internal_slot(
            calendar=calendar, op=op, batch=batch, machine_id="M1", operator_id="O1", base_time=BASE,
            prev_end=release, total_hours_base=hours, machine_timeline=state.machine_timeline["M1"],
            operator_timeline=state.operator_timeline["O1"], machine_downtimes=downtime,
            last_op_type_by_machine=state.last_op_type_by_machine, abort_after=None, end_dt_exclusive=cutoff)

    with sgs_handoff_scope(cache):
        if not shared:
            return compute()
        return cache.shared_slot_estimate(
            calendar=calendar, op=op, batch=batch, machine_id="M1", operator_id="O1", prev_end=release,
            total_hours=hours, end_dt_exclusive=cutoff, machine_downtimes=downtime, compute=compute)


def test_later_release_reuses_earliest_slot_but_recomputes_operation_changeover():
    with native_calendar() as calendar:
        cache, calls = _cache(calendar, spans((0, 2))), []
        first = _evaluate(cache, calendar, calls=calls)
        later = _evaluate(cache, calendar, release=at(1), op_id=2, op_type="MILL", calls=calls)
        assert calls == [1]
        assert (first.start_time, first.end_time) == (later.start_time, later.end_time) == (at(2), at(3))
        assert first.changeover_penalty == 1 and later.changeover_penalty == 0
        assert later == _evaluate(cache, calendar, release=at(1), op_id=2, op_type="MILL", shared=False)
        assert cache.stats()["shared_slot_hits"] == 1


@pytest.mark.parametrize("change", ["later", "hours", "priority", "cutoff", "downtime", "machine", "operator", "same_length"])
def test_changed_slot_inputs_cannot_borrow_a_stale_result(change):
    with native_calendar() as calendar:
        cache = _cache(calendar, spans((0, 2)))
        _evaluate(cache, calendar)
        kwargs = dict(release=at(1))
        if change == "later":
            kwargs["release"] = at(2.5)
        elif change == "hours":
            kwargs["hours"] = 2.0
        elif change == "priority":
            kwargs["priority"] = "urgent"
        elif change == "cutoff":
            kwargs["cutoff"] = at(3)
        elif change == "downtime":
            kwargs["downtime"] = spans((2, 4))
        elif change == "machine":
            occupy_resource(cache.state.machine_timeline, "M1", at(2), at(4))
        elif change == "operator":
            occupy_resource(cache.state.operator_timeline, "O1", at(2), at(4))
        else:
            cache.state.machine_timeline["M1"][0] = (at(0), at(4))
        assert _evaluate(cache, calendar, **kwargs) == _evaluate(cache, calendar, shared=False, **kwargs)
        assert cache.stats()["shared_slot_hits"] == 0


def test_earlier_release_can_fit_before_an_old_obstacle_and_must_be_recomputed():
    with native_calendar() as calendar:
        cache = _cache(calendar, spans((2, 3)))
        assert _evaluate(cache, calendar, release=at(1), hours=2.0).start_time == at(3)
        assert _evaluate(cache, calendar, hours=2.0).start_time == BASE
        assert cache.stats()["shared_slot_hits"] == 0


def test_cross_day_and_efficiency_change_are_not_constant_window_proofs():
    with native_calendar(rows=[day_row(1, efficiency=0.5)]) as calendar:
        cache = _cache(calendar, spans((0, 8)))
        first = _evaluate(cache, calendar)
        assert first.start_time.date() > BASE.date()
        later = _evaluate(cache, calendar, release=at(2), op_id=2)
        assert later == _evaluate(cache, calendar, release=at(2), op_id=2, shared=False)
        assert cache.stats()["shared_slot_hits"] == 0


def test_borrowed_nonempty_lists_and_instrumented_estimator_keep_every_probe(monkeypatch):
    with native_calendar() as calendar:
        cache, calls = _cache(calendar), []
        borrowed = spans((0, 2))
        dict.__setitem__(cache.state.machine_timeline, "M1", borrowed)
        _evaluate(cache, calendar, calls=calls)
        borrowed[0] = (at(0), at(3))
        assert _evaluate(cache, calendar, release=at(1), calls=calls).start_time == at(3)
        assert len(calls) == 2 and cache.stats()["shared_slot_hits"] == 0
        cache = _cache(calendar, spans((0, 2)))
        original = internal_slot._estimate_attempt
        attempts = []

        def observed(*args, **kwargs):
            attempts.append(kwargs["earliest"])
            return original(*args, **kwargs)

        monkeypatch.setattr(internal_slot, "_estimate_attempt", observed)
        _evaluate(cache, calendar)
        count = len(attempts)
        _evaluate(cache, calendar, release=at(1))
        assert len(attempts) > count and cache.stats()["shared_slot_hits"] == 0


def test_round_reset_discards_shared_slots_without_resetting_statistics():
    with native_calendar() as calendar:
        cache, calls = _cache(calendar, spans((0, 2))), []
        _evaluate(cache, calendar, calls=calls)
        _evaluate(cache, calendar, release=at(1), calls=calls)
        cache.next_round()
        _evaluate(cache, calendar, release=at(1), calls=calls)
        assert len(calls) == 2 and cache.stats()["shared_slot_hits"] == 1


def test_certified_round_still_checks_owner_revisions_and_instance_overrides():
    with native_calendar() as calendar:
        cache = _cache(calendar, spans((0, 2)))
        cache.begin_round()
        _evaluate(cache, calendar)
        values = cache.state.machine_timeline["M1"]
        values[0] = (at(0), at(3))
        assert _evaluate(cache, calendar, release=at(1)).start_time == at(3)
        old = values.certificate()
        values.certificate = lambda: old
        values[0] = (at(0), at(4))
        assert _evaluate(cache, calendar, release=at(1)).start_time == at(4)
        assert cache.stats()["shared_slot_hits"] == 0


def test_new_round_rejects_changed_owner_protocol(monkeypatch):
    from collections.abc import MutableSequence

    with native_calendar() as calendar:
        cache = _cache(calendar, spans((0, 2)))
        cache.begin_round()
        _evaluate(cache, calendar)
        monkeypatch.setattr(MutableSequence, "append", lambda owner, row: owner._values.__setitem__(0, row))
        cache.state.machine_timeline["M1"].append((at(0), at(4)))
        cache.next_round()
        cache.begin_round()
        assert _evaluate(cache, calendar, release=at(1)).start_time == at(4)
        assert cache.stats()["shared_slot_hits"] == 0


def test_random_gaps_hours_and_releases_match_full_estimator():
    rng = random.Random(20260915)
    with native_calendar() as calendar:
        for _ in range(12):
            occupied = []
            for index in range(6):
                start = index * 0.75
                occupied.append((at(start), at(start + rng.choice((0.15, 0.5, 0.75)))))
            cache = _cache(calendar, occupied)
            for release in [at(rng.randrange(0, 20) / 4) for _ in range(16)]:
                kwargs = dict(release=release, hours=rng.choice((0.25, 0.5, 1.0)), op_id=rng.randrange(1, 100))
                assert _evaluate(cache, calendar, **kwargs) == _evaluate(cache, calendar, shared=False, **kwargs)
