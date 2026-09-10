"""Exact reuse/invalidation contracts; no wall-clock assertions or database access."""

import random
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, Dict

import pytest

from core.algorithm_runtime.downtime import SegmentOverlapIndex, occupy_resource
from core.algorithm_runtime.internal_slot import estimate_internal_slot
from core.algorithm_runtime.run_state import ScheduleRunState
from core.algorithm_runtime.slot_overlap_reuse import SlotOverlapReuse, overlap_reuse_for, sgs_overlap_reuse
from tests._support.sgs_slot_reuse_case import BASE


def dt(hours):
    return BASE + timedelta(hours=hours)


class Calendar:
    efficiency = 1.0

    def adjust_to_working_time(self, start, priority=None, operator_id=None):
        return start

    def get_efficiency(self, start, operator_id=None):
        return self.efficiency

    def add_working_hours(self, start, hours, priority=None, operator_id=None):
        return start + timedelta(hours=hours)


def slot_args() -> Dict[str, Any]:
    return dict(
        calendar=Calendar(), op=SimpleNamespace(setup_hours=0.5, unit_hours=0.0, op_type_name="T1"),
        batch=SimpleNamespace(quantity=1, priority="normal"), machine_id="M1", operator_id="W1",
        base_time=BASE, prev_end=BASE, machine_timeline=[(dt(0), dt(1)), (dt(1), dt(2))],
        operator_timeline=[(dt(2), dt(3))], machine_downtimes=[(dt(3), dt(4))],
        last_op_type_by_machine={"M1": "T1"}, end_dt_exclusive=None, abort_after=None,
    )


def test_probe_score_placement_share_materialized_indexes(monkeypatch):
    calls = []
    original = SegmentOverlapIndex._materialize

    def materialize(self):
        calls.append(self)
        return original(self)

    monkeypatch.setattr(SegmentOverlapIndex, "_materialize", materialize)
    reuse, kwargs = SlotOverlapReuse(), slot_args()
    estimates = [estimate_internal_slot(**kwargs, overlap_reuse=reuse) for _ in range(3)]
    assert len(calls) == 3
    assert estimates[0] == estimates[1] == estimates[2]
    assert estimates[0].start_time == dt(4)


@pytest.mark.parametrize("kind, field, resource", [
    ("machine", "machine_timeline", "M1"), ("operator", "operator_timeline", "W1"),
    ("downtime", "machine_downtimes", "M1"),
])
@pytest.mark.parametrize("mutation", ["append", "same_length", "replace", "clear", "gap_insert", "invalid_segment"])
def test_every_segment_change_invalidates_only_affected_resource(kind, field, resource, mutation):
    reuse, kwargs = SlotOverlapReuse(), slot_args()
    estimate_internal_slot(**kwargs, overlap_reuse=reuse)
    old = reuse.index(kind, resource, kwargs[field])
    untouched = reuse.index("machine", "OTHER", [(dt(10), dt(11))])
    segments = kwargs[field]
    if mutation == "append":
        segments.append((dt(4), dt(6)))
    elif mutation == "same_length":
        segments[-1] = (segments[-1][0], dt(6))
    elif mutation == "replace":
        kwargs[field] = [(dt(0), dt(6))]
    elif mutation == "clear":
        segments.clear()
    elif mutation == "gap_insert":
        occupy_resource({resource: segments}, resource, dt(-1), dt(0.25))
    else:
        segments.append((dt(10), dt(9)))
    assert reuse.index(kind, resource, kwargs[field]) is not old
    assert reuse.index("machine", "OTHER", [(dt(10), dt(11))]) is untouched
    assert estimate_internal_slot(**kwargs, overlap_reuse=reuse) == estimate_internal_slot(**kwargs)


def test_reused_index_holds_immutable_snapshot_not_mutable_timeline():
    reuse = SlotOverlapReuse()
    segments = [(dt(0), dt(1))]
    old = reuse.index("machine", "M1", segments)
    old.shift_end(dt(0), dt(0.5))
    old.shift_end(dt(0), dt(0.5))
    segments[0] = (dt(0), dt(9))
    assert old.shift_end(dt(0), dt(0.5)) == dt(1)
    assert reuse.index("machine", "M1", segments).shift_end(dt(0), dt(0.5)) == dt(9)


def test_same_ids_in_separate_resource_domains_do_not_alias():
    reuse = SlotOverlapReuse()
    segments = [(dt(0), dt(1))]
    indexes = [reuse.index(kind, "R", segments) for kind in ("machine", "operator", "downtime")]
    assert len({id(index) for index in indexes}) == 3
    assert reuse.index("machine", "R2", segments) is not indexes[0]


def test_unsorted_zero_hop_does_not_materialize_across_estimates():
    reuse, kwargs = SlotOverlapReuse(), slot_args()
    kwargs.update(machine_timeline=[(dt(2), dt(3)), (dt(0), dt(1))], operator_timeline=[], machine_downtimes=[])
    for _ in range(4):
        assert estimate_internal_slot(**kwargs, overlap_reuse=reuse) == estimate_internal_slot(**kwargs)
    kwargs.update(base_time=dt(2), prev_end=dt(2))
    for enabled in (False, True):
        with pytest.raises(ValueError, match="重叠索引要求"):
            estimate_internal_slot(**kwargs, overlap_reuse=reuse if enabled else None)


@pytest.mark.parametrize("change", ["base_time", "prev_end", "hours", "quantity", "priority", "last_type",
                                     "window_equal", "abort_early", "abort_late", "efficiency", "fallback", "zero"])
def test_non_segment_inputs_are_always_recomputed(change):
    reuse, kwargs = SlotOverlapReuse(), slot_args()
    estimate_internal_slot(**kwargs, overlap_reuse=reuse)
    if change in ("base_time", "prev_end"):
        kwargs[change] = dt(7)
    elif change == "hours":
        kwargs["op"].setup_hours = 2.0
    elif change == "quantity":
        kwargs["op"].unit_hours = 0.5
        kwargs["batch"].quantity = 4
    elif change == "priority":
        kwargs["batch"].priority = "urgent"
    elif change == "last_type":
        kwargs["last_op_type_by_machine"]["M1"] = "T2"
    elif change == "window_equal":
        kwargs["end_dt_exclusive"] = dt(4.5)
    elif change in ("abort_early", "abort_late"):
        kwargs["abort_after"] = dt(-1 if change == "abort_early" else 2.5)
    elif change in ("efficiency", "fallback"):
        kwargs["calendar"].efficiency = 0.5 if change == "efficiency" else None
    else:
        kwargs["op"].setup_hours = 0.0
    actual = estimate_internal_slot(**kwargs, overlap_reuse=reuse)
    assert actual == estimate_internal_slot(**kwargs)
    if change == "window_equal":
        assert actual.blocked_by_window
    if change in ("abort_early", "abort_late"):
        assert actual.abort_after_hit
    if change == "fallback":
        assert actual.efficiency_fallback_used


def test_cache_lifetime_cleanup_on_success_exception_and_next_run():
    state = ScheduleRunState(base_time=BASE)
    assert overlap_reuse_for(state.machine_timeline) is None
    with sgs_overlap_reuse(state.machine_timeline):
        first = overlap_reuse_for(state.machine_timeline)
        assert first is not None
        assert overlap_reuse_for(ScheduleRunState(base_time=BASE).machine_timeline) is None
    assert overlap_reuse_for(state.machine_timeline) is None
    with pytest.raises(RuntimeError, match="stop"):
        with sgs_overlap_reuse(state.machine_timeline):
            assert overlap_reuse_for(state.machine_timeline) is not first
            raise RuntimeError("stop")
    assert overlap_reuse_for(state.machine_timeline) is None


def test_random_interleaved_resource_updates_match_uncached_estimator():
    rng, reuse, kwargs = random.Random(20260908), SlotOverlapReuse(), slot_args()
    for _ in range(120):
        field = rng.choice(["machine_timeline", "operator_timeline", "machine_downtimes"])
        segments = kwargs[field]
        start = rng.randrange(-2, 30)
        segment = (dt(start), dt(start + rng.choice([-1, 0, 0.5, 2, 4])))
        if segments and rng.random() < 0.5:
            segments[rng.randrange(len(segments))] = segment
        else:
            segments.append(segment)
        segments.sort()
        kwargs["op"].setup_hours = rng.choice([0, 0.5, 2])
        kwargs["prev_end"] = dt(rng.randrange(0, 20))
        assert estimate_internal_slot(**kwargs, overlap_reuse=reuse) == estimate_internal_slot(**kwargs)


def test_legacy_borrowed_timeline_alias_and_dict_semantics_are_preserved():
    timeline = {"M1": [(dt(0), dt(1))]}
    state = ScheduleRunState(base_time=BASE, machine_timeline=timeline)
    with sgs_overlap_reuse(state.machine_timeline):
        assert overlap_reuse_for(state.machine_timeline) is None
        occupy_resource(state.machine_timeline, "M1", dt(1), dt(2))
    assert state.machine_timeline is timeline
    assert timeline["M1"] == [(dt(0), dt(1)), (dt(1), dt(2))]
