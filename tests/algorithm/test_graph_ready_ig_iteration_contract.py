"""A paused IG trial gives time back without charging other stages or losing its incumbent."""
from __future__ import annotations

import random
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_acceptance import PoolEntry
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_contract import (
    IteratedGreedyLimits,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_iteration import IGIteration
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_moves import _Parent
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_neighborhoods import (
    GeneratorRotation,
    build_generators,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_run import IteratedGreedyRun


def _iteration_fixture():
    now = [0.0]
    limits = IteratedGreedyLimits(destruction_size=1, insertion_window=4)
    report = new_iterated_greedy_report(limits, objective_name="min_overdue")
    reference = PoolEntry((1, 2, 3, 4), (0.0, 10.0), {})
    generators = build_generators(("tardy_random",), initial_size=1, max_size=6)
    search = SimpleNamespace(
        clock=lambda: now[0], limits=limits, report=report, scored_decodes=0,
        rnd=random.Random(0), rotation=GeneratorRotation(generators),
        parent=_Parent(reference.order, ("B",), (), {i: set() for i in reference.order},
                       {i: set() for i in reference.order}),
        idle_iterations=0, rejected_iterations=0, non_improving=0, improved_incumbent=False,
        _require_budget=lambda: None, _reference_for_iteration=lambda: reference,
        _features=lambda entry: {"signals": {}}, _accept_walk=lambda entry, previous: None,
    )

    def score(order, _reference=None):
        now[0] += 0.25
        report["decodes"] += 1
        search.scored_decodes += 1
        return (0.0, float(sum((index + 1) * op for index, op in enumerate(order)))), True

    search._score_trial = score
    search._decode_entry = lambda order: PoolEntry(order, score(order)[0], {}, decoded_order=True)
    return IGIteration(search), search, generators[0], now


def test_each_trial_yields_and_feedback_excludes_other_stages_wall_time():
    iteration, search, generator, now = _iteration_fixture()
    tasks = 0
    while True:
        before = search.report["decodes"]
        continuing = iteration.step()
        assert search.report["decodes"] - before <= 1
        tasks += 1
        if not continuing:
            break
        now[0] += 100.0  # Another solver runs while this iteration is suspended.
    assert tasks >= 4
    assert search.report["iterations"] == generator.calls == 1
    assert search.report["interrupted_iterations"] == 0
    assert generator.time_seconds == pytest.approx(search.report["decodes"] * 0.25)


def test_closing_a_paused_iteration_accounts_and_shrinks_it_once():
    iteration, search, generator, now = _iteration_fixture()
    previous_difficulty = generator.difficulty.value
    assert iteration.step()
    now[0] += 500.0
    iteration.close()
    iteration.close()
    assert search.report["iterations"] == 0
    assert search.report["interrupted_iterations"] == generator.calls == 1
    assert generator.fully_solved == 0 and generator.difficulty.value < previous_difficulty
    assert generator.time_seconds == pytest.approx(0.25)


def test_shared_incumbent_is_visible_mid_iteration_but_context_adoption_waits(monkeypatch):
    old, improved = {"score": (0, 10)}, {"score": (0, 5)}
    adopted = []
    search = SimpleNamespace(best=old, adopt_incumbent=lambda candidate, profile: adopted.append((candidate, profile)))
    observed = []

    class PendingIteration:
        def step(self):
            observed.append(search.best)
            return False

    run = IteratedGreedyRun.__new__(IteratedGreedyRun)
    run.search = search
    run.state = SimpleNamespace(best=improved)
    run.pending_adoption = None
    run.iteration = PendingIteration()
    run.parent_profile = lambda candidate: "new-profile"
    run.report = {"iterations": 1, "stop_reason": None}
    run.limits = IteratedGreedyLimits(max_iterations=2)
    run.stopped = False
    run._advance()
    assert observed == [improved] and adopted == [] and search.best is improved
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_run as run_module
    monkeypatch.setattr(run_module, "IGIteration", lambda search: PendingIteration())
    run._advance()
    assert adopted == [(improved, "new-profile")]
    run.report["iterations"] = 2
    adopted.clear()
    run._advance()
    assert adopted == []
    assert run.stopped and run.report["stop_reason"] == "max_iterations"


def test_failed_trials_are_not_decoded_again_as_the_final_iteration_order(monkeypatch):
    from core.infrastructure.errors import ValidationError
    from tests.algorithm.test_graph_ready_ig_incumbent_context_contract import _Harness

    harness = _Harness(strict_mode=False)
    harness.start()
    failed_orders = []

    def reject_after_real_decode(kwargs, candidate):
        failed_orders.append(tuple(kwargs["repair_decision"].operation_order))
        raise ValidationError("controlled deterministic rejection", field="schedule")

    harness.after_evaluate = reject_after_real_decode
    for generator in harness.search.generators:
        monkeypatch.setattr(generator, "select", lambda *args, **kwargs: (1, 2))
    decodes_before = harness.report["decodes"]
    pruned_before = harness.report["duplicate_decision_pruned"]
    rejected_before = sum(harness.report["rejected_by_reason"].values())
    iteration = IGIteration(harness.search)
    while iteration.step():
        pass

    # Every rejection followed an actual SGS call; the parked final order was already rejected.
    assert len(failed_orders) == len(set(failed_orders)) == len(harness.schedule_calls) == 6
    assert failed_orders.count((3, 4, 2, 1)) == 1
    assert harness.report["decodes"] - decodes_before == len(failed_orders)
    assert sum(harness.report["rejected_by_reason"].values()) - rejected_before == len(failed_orders)
    assert harness.report["duplicate_decision_pruned"] > pruned_before
    assert harness.report["iterations"] == 1 and harness.report["interrupted_iterations"] == 0
    harness.assert_initial_incumbent()
