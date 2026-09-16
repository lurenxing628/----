"""Building blocks of the iterated greedy stage, checked against the OR-Tools mechanisms they port.

Adaptive destroy size (AdaptiveParameterValue), coherent time/resource windows, successful-generator
continuation (CompoundOperator), simulated annealing with fixed-scale exponential cooling
(routing ILS), the diverse solution pool (SharedSolutionRepository) and checkpoint selection for trials.
"""
from __future__ import annotations

import math
import random
from dataclasses import replace

import pytest

from core.algorithms.greedy.dispatch.sgs_checkpoint import DecodeCheckpoint
from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_acceptance as acceptance
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_acceptance import (
    ExponentialCooling,
    PoolEntry,
    SolutionPool,
    TemperatureScale,
    profile_identity,
    sa_accept,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_checkpoints import (
    CheckpointStore,
    checkpoint_positions,
    common_prefix_length,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_neighborhoods import (
    AdaptiveValue,
    GeneratorRotation,
    ResourceWindowGenerator,
    TardyRandomGenerator,
    TimeWindowGenerator,
    build_generators,
)
from core.services.scheduler.run.optimizer_graph_ready_profiles import GraphReadyWeightProfile

# ---- adaptive destroy size ------------------------------------------------------------------------------------------

def test_adaptive_value_follows_the_or_tools_update_formulas():
    value = AdaptiveValue(0.5)
    value.increase()  # f = 1 + 1/sqrt(2)
    factor = 1.0 + 1.0 / math.sqrt(2.0)
    assert value.value == pytest.approx(min(1.0 - 0.5 / factor, 0.5 * factor))
    before = value.value
    value.decrease()  # f = 1 + 1/sqrt(3)
    factor = 1.0 + 1.0 / math.sqrt(3.0)
    assert value.value == pytest.approx(max(before / factor, 1.0 - (1.0 - before) * factor))
    assert value.num_changes == 2
    saturating = AdaptiveValue(0.9)
    for _ in range(50):
        saturating.increase()
    assert saturating.value <= 1.0
    shrinking = AdaptiveValue(0.1)
    for _ in range(50):
        shrinking.decrease()
    assert shrinking.value >= 0.0
    with pytest.raises(ValueError):
        AdaptiveValue(1.5)


def test_generator_size_grows_when_idle_and_shrinks_when_cut_short():
    generator, = build_generators(["time_window"], initial_size=3, max_size=6)
    assert generator.size() == 3
    generator.record(0.1, improved=False, fully_solved=True, idle=True)
    assert generator.size() > 3
    for _ in range(6):
        generator.record(0.1, improved=False, fully_solved=False, idle=False)
    assert generator.size() == 1
    # A completed iteration that changed the order keeps the size.
    before = generator.difficulty.value
    generator.record(0.1, improved=True, fully_solved=True, idle=False)
    assert generator.difficulty.value == before
    summary = generator.summary()
    assert summary["calls"] == 8 and summary["improving"] == 1 and summary["idle"] == 1 and summary["fully_solved"] == 2
    with pytest.raises(ValidationError):
        build_generators(["nope"], initial_size=1, max_size=2)
    with pytest.raises(ValueError):
        build_generators(["time_window"], initial_size=4, max_size=3)


def test_complete_worse_iteration_shrinks_and_restart_resets_sizes_without_erasing_counts():
    generators = build_generators(["time_window", "resource_window", "tardy_random"], initial_size=3, max_size=6)
    rotation = GeneratorRotation(generators)
    generators[0].record(0.3, improved=False, fully_solved=True, idle=False, worse=True)
    generators[1].record(0.2, improved=False, fully_solved=True, idle=True)
    generators[2].record(0.1, improved=True, fully_solved=True, idle=False)
    assert generators[0].size() < 3 < generators[1].size()
    before = [(item.calls, item.improving, item.time_seconds) for item in generators]
    rotation.reset_sizes()
    assert [item.size() for item in generators] == [3, 3, 3]
    assert all(item.difficulty.num_changes == 0 for item in generators)
    assert [(item.calls, item.improving, item.time_seconds) for item in generators] == before


@pytest.mark.parametrize("initial_size", [1, 6])
def test_initial_size_at_either_limit_can_still_adapt(initial_size):
    generator = TimeWindowGenerator(initial_size=initial_size, max_size=6)
    assert generator.size() == initial_size
    generator.record(0.1, improved=False, fully_solved=True, idle=initial_size == 1, worse=initial_size == 6)
    assert 1 < generator.size() < 6
    generator.reset()
    assert generator.size() == initial_size and generator.calls == 1


# ---- coherent neighbourhoods ----------------------------------------------------------------------------------------

def _features(order, *, starts=None, machines=None, signals=None):
    return {
        "starts": starts if starts is not None else {op: float(index) for index, op in enumerate(order)},
        "machines": machines if machines is not None else {},
        "signals": signals if signals is not None else {},
    }


def test_time_window_removes_a_contiguous_block_by_decoded_start():
    order = (5, 1, 4, 2, 3)
    starts = {5: 40.0, 1: 0.0, 4: 30.0, 2: 10.0, 3: 20.0}  # start order: 1, 2, 3, 4, 5
    generator, = build_generators(["time_window"], initial_size=2, max_size=4)
    seen = set()
    for seed in range(20):
        removed = generator.select(order, size=2, rnd=random.Random(seed), features=_features(order, starts=starts))
        assert len(removed) == 2
        seen.add(removed)
    assert seen <= {(1, 2), (2, 3), (3, 4), (4, 5)} and len(seen) >= 2
    assert generator.select((7,), size=2, rnd=random.Random(0), features=_features((7,))) == ()
    # Never removes the whole order.
    assert len(generator.select(order, size=9, rnd=random.Random(0), features=_features(order, starts=starts))) == 4


def test_resource_window_stays_on_one_machine_and_degenerates_only_when_no_machine_has_two_operations():
    order = (1, 2, 3, 4, 5, 6)
    starts = {op: float(op) for op in order}
    machines = {1: "M1", 2: "M2", 3: "M1", 4: "M2", 5: "M1", 6: ""}
    generator, = build_generators(["resource_window"], initial_size=2, max_size=4)
    for seed in range(20):
        removed = generator.select(order, size=2, rnd=random.Random(seed), features=_features(order, starts=starts, machines=machines))
        assert len(removed) == 2 and len({machines[op] for op in removed}) == 1
        assert removed in {(1, 3), (3, 5), (2, 4)}
    assert generator.degenerate == 0
    singles = {op: "M" + str(op) for op in order}
    removed = generator.select(order, size=2, rnd=random.Random(1), features=_features(order, starts=starts, machines=singles))
    assert len(removed) == 2 and generator.degenerate == 1


def test_tardy_random_prefers_signals():
    order = tuple(range(1, 11))
    signals = {op: 0.0 for op in order}
    signals.update({4: 5.0, 7: 2.0, 9: 1e-3})
    generator = TardyRandomGenerator(initial_size=4, max_size=6)
    removed = generator.select(order, size=4, rnd=random.Random(3), features=_features(order, signals=signals))
    assert len(removed) == len(set(removed)) == 4 and removed[0] == 4 and removed[1] == 7


def test_rotation_repeats_success_then_advances_once_after_each_failed_call():
    generators = build_generators(["time_window", "resource_window", "tardy_random"], initial_size=3, max_size=6)
    assert [type(item) for item in generators] == [TimeWindowGenerator, ResourceWindowGenerator, TardyRandomGenerator]
    rotation = GeneratorRotation(generators)
    assert rotation.pick() is generators[0]
    # Even a long successful call continues with the same generator.
    generators[0].record(10.0, improved=True, fully_solved=True, idle=False)
    assert rotation.pick() is generators[0]
    generators[0].record(0.1, improved=True, fully_solved=True, idle=False)
    assert rotation.pick() is generators[0]
    generators[0].record(0.1, improved=False, fully_solved=True, idle=True)
    assert rotation.pick() is generators[1]
    # Merely inspecting the choice twice must not skip an untried generator.
    assert rotation.pick() is generators[1]
    generators[1].record(0.1, improved=False, fully_solved=False, idle=False)
    assert rotation.pick() is generators[2]
    generators[2].record(0.1, improved=False, fully_solved=True, idle=False, worse=True)
    assert rotation.pick() is generators[0]
    assert sum(item.calls for item in generators) == 5
    single = GeneratorRotation([generators[0]])
    generators[0].record(0.1, improved=False, fully_solved=True, idle=False)
    assert single.pick() is generators[0]


# ---- acceptance -----------------------------------------------------------------------------------------------------

def test_exponential_cooling_and_temperature_scale():
    cooling = ExponentialCooling(0.1, 0.001)
    assert cooling.temperature(0.0, 0.5) == 0.0
    assert cooling.temperature(20.0, 0.0) == pytest.approx(2.0)
    assert cooling.temperature(20.0, 1.0) == pytest.approx(0.02)
    assert cooling.temperature(20.0, 0.5) == pytest.approx(2.0 * 0.01 ** 0.5)
    assert cooling.temperature(20.0, 7.0) == pytest.approx(0.02)  # progress is clamped
    with pytest.raises(ValueError):
        ExponentialCooling(0.001, 0.1)
    scale = TemperatureScale()
    assert scale.value == 0.0
    scale.observe((0.0, 12.0, 1.0), (0.0, 10.0, 5.0))
    scale.observe((0.0, 10.0, 9.0), (0.0, 10.0, 5.0))  # equal primary: ignored
    scale.observe((1.0, 3.0), (0.0, 10.0))  # different failed_ops: ignored
    scale.observe((0.0, 4.0), (0.0, 10.0))
    assert scale.count == 2 and scale.total == pytest.approx(8.0) and scale.value == pytest.approx(2.0)


def test_later_large_deltas_cannot_reheat_the_exponential_schedule():
    scale = TemperatureScale()
    cooling = ExponentialCooling(0.1, 0.001)
    reference = (0.0, 10.0)
    scale.observe((0.0, math.inf), reference)
    scale.observe((0.0, math.nan), reference)
    scale.observe((1.0, 11.0), reference)
    assert scale.count == 0 and scale.value == 0.0
    scale.observe((0.0, 11.0), reference)
    initial = cooling.temperature(scale.value, 0.0)
    scale.observe((0.0, 110.0), reference)
    middle = cooling.temperature(scale.value, 0.5)
    scale.observe((0.0, 1e9), reference)
    final = cooling.temperature(scale.value, 1.0)
    assert scale.value == 1.0 and initial > middle > final > 0.0
    assert (initial, middle, final) == pytest.approx((0.1, 0.01, 0.001))


def test_sa_accept_is_the_ils_criterion_on_the_primary_objective_only():
    reference = (0.0, 10.0, 5.0)
    assert sa_accept((0.0, 9.0, 99.0), reference, temperature=0.0, u=0.5)
    assert sa_accept((0.0, 10.0, 5.0), reference, temperature=0.0, u=0.5)
    assert sa_accept((0.0, 10.0, 4.0), reference, temperature=100.0, u=0.5)
    assert not sa_accept((0.0, 10.0, 6.0), reference, temperature=100.0, u=0.5)
    assert not sa_accept((0.0, 11.0, 0.0), reference, temperature=0.0, u=0.5)
    # candidate + T * log(u) < reference: 11 + 2 * log(0.5) = 9.61 < 10 accepts, u = 0.9 does not.
    assert sa_accept((0.0, 11.0, 0.0), reference, temperature=2.0, u=0.5)
    assert not sa_accept((0.0, 11.0, 0.0), reference, temperature=2.0, u=0.9)
    assert not sa_accept((1.0, 0.0, 0.0), reference, temperature=1e9, u=0.5)  # failed operations are never traded
    assert sa_accept((0.0,), (0.0,), temperature=1.0, u=0.5)
    with pytest.raises(ValueError):
        sa_accept((), reference, temperature=1.0, u=0.5)


def test_solution_pool_keeps_distinct_best_orders_and_picks_biased_to_the_best():
    pool = SolutionPool(2)
    first = PoolEntry(order=(1, 2), score=(0.0, 5.0), candidate={})
    second = PoolEntry(order=(2, 1), score=(0.0, 3.0), candidate={})
    third = PoolEntry(order=(1, 3), score=(0.0, 3.0), candidate={})
    assert pool.add(first) and pool.add(second) and pool.add(third)
    assert [item.order for item in pool.entries] == [(2, 1), (1, 3)]  # the worst entry was dropped
    assert not pool.add(PoolEntry(order=(2, 1), score=(0.0, 1.0), candidate={}))  # duplicate order
    assert not pool.add(PoolEntry(order=(9, 9), score=(0.0, 9.0), candidate={}))  # worse than the pool
    picks = {pool.pick(random.Random(seed)).order for seed in range(30)}
    assert picks == {(2, 1), (1, 3)}  # uniform among tied best entries
    assert pool.pick(random.Random(0), exclude_order=(2, 1)).order == (1, 3)
    assert SolutionPool(1).pick(random.Random(0)) is None
    with pytest.raises(ValueError):
        SolutionPool(0)


@pytest.mark.parametrize("decoded_score", [0.5, 2.0, 3.0])
def test_pool_refresh_replaces_formal_decode_payload_and_resorts_without_losing_selection_history(decoded_score):
    pool = SolutionPool(2)
    imported = PoolEntry((1, 2), (0.0, 1.0), {"source": "elite"}, checkpoints=["old"], features={"old": True},
                         batch_order=("A", "B"), resource_overrides=((1, "M1", "P1"),))
    other = PoolEntry((2, 1), (0.0, 2.0), {})
    assert pool.add(imported) and pool.add(other)
    for _ in range(3):
        assert pool.pick(random.Random(0)) is imported
    decoded = replace(imported, score=(0.0, decoded_score), candidate={"source": "formal"},
                      checkpoints=["new"], features=None, num_selected=0, sequence=0)
    assert not pool.add(decoded)  # Ordinary observations still cannot overwrite the existing decision.
    assert pool.refresh(decoded)
    assert decoded.num_selected == 3 and decoded.sequence == imported.sequence
    assert len(pool.entries) == 2 and not any(item is imported for item in pool.entries)
    assert next(item for item in pool.entries if item.decision_key() == imported.decision_key()) is decoded
    assert decoded.candidate == {"source": "formal"} and decoded.checkpoints == ["new"] and decoded.features is None
    assert [item.score for item in pool.entries] == sorted([(0.0, decoded_score), other.score])
    assert pool.entries[0] is (decoded if decoded_score <= 2.0 else other)


def test_pool_refresh_of_new_decision_keeps_context_identity_and_bounded_diversity():
    pool = SolutionPool(3)
    base = PoolEntry((1, 2, 3, 4), (0.0, 1.0), {}, resource_overrides=((1, "M1", "P1"),))
    new_context = replace(base, resource_overrides=((1, "M2", "P1"),))
    near = PoolEntry((1, 2, 4, 3), (0.0, 1.0), {})
    distant = PoolEntry((4, 3, 2, 1), (0.0, 1.0), {})
    assert pool.add(base) and pool.refresh(new_context) and pool.add(near)
    assert len(pool.entries) == 3 and base.decision_key() != new_context.decision_key()
    assert pool.refresh(distant)
    assert len(pool.entries) == 3 and any(item is distant for item in pool.entries)
    assert len({item.decision_key() for item in pool.entries}) == 3
    assert not pool.refresh(PoolEntry((8, 7, 6, 5), (0.0, 2.0), {}))
    assert all(item.score == (0.0, 1.0) for item in pool.entries)


def _pool_profile():
    return GraphReadyWeightProfile(slug="test", profile_order=0, raw_weights={"a": 0.2, "b": 0.8},
                                   effective_weights={"a": 0.2, "b": 0.8}, candidate_origin="graph_ready_v2",
                                   candidate_policy="test", formula_version="graph_ready_v2")


def test_pool_identity_preserves_resource_batch_and_stable_profile_context():
    profile = _pool_profile()
    entry = PoolEntry((1, 2), (0.0, 1.0), {}, batch_order=("A", "B"),
                      resource_overrides=((1, "M1", "P1"), (2, "M2", "P2")), profile=profile)
    copied_profile = replace(profile, raw_weights={"b": 0.8, "a": 0.2})
    duplicate = replace(entry, candidate={"different_object": True}, profile=copied_profile,
                        resource_overrides=tuple(reversed(entry.resource_overrides)))
    assert profile is not copied_profile and profile_identity(profile) == profile_identity(copied_profile)
    assert entry.decision_key() == duplicate.decision_key()
    assert hash(entry.decision_key()) == hash(duplicate.decision_key())
    pool = SolutionPool(8)
    assert pool.add(entry) and not pool.add(duplicate)
    variants = [replace(entry, resource_overrides=((1, "M3", "P1"), (2, "M2", "P2"))),
                replace(entry, batch_order=("B", "A")),
                replace(entry, profile=replace(profile, formula_slug="another_formula")),
                replace(entry, profile=replace(profile, effective_weights={"a": 0.8, "b": 0.2}))]
    assert all(pool.add(variant) for variant in variants)
    picks = {pool.pick(random.Random(seed), exclude_entry=duplicate).decision_key() for seed in range(40)}
    assert picks == {item.decision_key() for item in variants}


def test_pool_retains_distant_equal_score_starts_without_sacrificing_better_scores():
    pool = SolutionPool(3)
    orders = [(1, 2, 3, 4), (1, 2, 4, 3), (1, 3, 2, 4), (4, 3, 2, 1)]
    for order in orders:
        pool.add(PoolEntry(order, (0.0, 1.0), {}))
    assert len(pool.entries) == 3 and orders[-1] in [item.order for item in pool.entries]
    assert orders[0] in [item.order for item in pool.entries]
    strictly_better = PoolEntry((1, 4, 2, 3), (0.0, 0.5), {})
    assert pool.add(strictly_better) and pool.entries[0] is strictly_better
    assert not pool.add(PoolEntry((8, 7, 6, 5), (0.0, 2.0), {}))
    assert pool.entries[0] is strictly_better and all(item.score <= (0.0, 1.0) for item in pool.entries)


def test_pool_diversity_distance_work_is_bounded_to_current_pool_and_new_entry(monkeypatch):
    measured = []
    distance = acceptance._entry_distance

    def measure(left, right):
        measured.append((left.order, right.order))
        return distance(left, right)

    monkeypatch.setattr(acceptance, "_entry_distance", measure)
    pool = SolutionPool(8)
    order = tuple(range(40))
    for offset in range(9):
        pool.add(PoolEntry(order[offset:] + order[:offset], (0.0, 1.0), {}))
    assert len(pool.entries) == 8 and len(measured) == 36
    for invalid in (9, True, 1.5):
        with pytest.raises(ValueError):
            SolutionPool(invalid)


# ---- checkpoint selection -------------------------------------------------------------------------------------------

def _checkpoint(position, prefix):
    return DecodeCheckpoint(position=position, prefix_op_ids=tuple(prefix), picked_op_ids=tuple(prefix), signature="s",
                            state=None, next_idx={}, graph_progress={}, warnings=())  # type: ignore[arg-type]


def test_checkpoint_positions_and_prefix_selection():
    assert checkpoint_positions(40, 8) == [4, 9, 13, 18, 22, 27, 31, 36]
    assert checkpoint_positions(3, 8) == [1, 2]
    assert checkpoint_positions(1, 8) == [] and checkpoint_positions(40, 0) == []
    assert common_prefix_length((1, 2, 3), (1, 2, 4)) == 2 and common_prefix_length((1,), (2,)) == 0
    store = CheckpointStore(8)
    base = tuple(range(1, 11))
    checkpoints = [_checkpoint(3, base[:3]), _checkpoint(6, base[:6]), _checkpoint(8, base[:8])]
    trial = (1, 2, 3, 4, 5, 6, 8, 7, 9, 10)
    assert store.best_for(checkpoints, base_order=base, trial_order=trial).position == 6
    assert store.best_for(checkpoints, base_order=base, trial_order=(2, 1) + base[2:]) is None
    assert CheckpointStore(0).best_for(checkpoints, base_order=base, trial_order=trial) is None
    request, captured = store.request_for(40)
    assert request is not None and set(request.positions) == set(checkpoint_positions(40, 8)) and captured == []
    assert CheckpointStore(0).request_for(40) == (None, [])
    store.note_decode(10, resumed_from=None)
    store.note_decode(10, resumed_from=checkpoints[1])
    assert store.summary() == {"count": 8, "full_decodes": 1, "resumed_decodes": 1, "picks_total": 20, "picks_saved": 6,
                               "equivalence_checks": 0}
