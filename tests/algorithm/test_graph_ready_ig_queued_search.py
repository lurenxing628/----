"""A misleading insertion hint must leave budgeted opportunities to improve."""
from types import SimpleNamespace

import pytest

from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_local as local
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_diversify import (
    BudgetStagnation,
    extended_positions,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_local import LargeIGIteration, NeighborhoodBudget


def _finish(generator):
    while True:
        try:
            next(generator)
        except StopIteration as result:
            return result.value


@pytest.mark.parametrize("first", [None, ((12,), True), ((1,), False)])
def test_rejected_or_non_improving_first_position_does_not_hide_second(first):
    original = (1, 2, 3, 4)
    reference = SimpleNamespace(order=original, score=(10,))
    calls = []
    report = {"decodes": 0, "local_search": {"queue_budget_stops": 0, "queue_continuations": 0,
                                           "shortlisted_positions": 0, "queue_exhausted": 0}}
    search = SimpleNamespace(report=report, scores={original: ((10,), True)},
                             limits=SimpleNamespace(insertion_window=6),
                             parent=SimpleNamespace(predecessors={2: set()}, successors={2: set()}),
                             clock=lambda: 0.0, _require_budget=lambda: None,
                             local_budget=SimpleNamespace(can_try=lambda reserve=0: True))

    def score(order, _reference):
        calls.append(order)
        report["decodes"] += 1
        return first if len(calls) == 1 else ((5,), True)

    search._score_trial = score
    iteration = LargeIGIteration(search)
    iteration.walk = None
    iteration.pending_insertions = 0
    screen = SimpleNamespace(ranked_positions=lambda *a, **k: [0, 2, 3])
    result = _finish(iteration._insert(screen, reference, list(original), 2, False))
    assert calls == [(2, 1, 3, 4), (1, 3, 2, 4)]
    assert result == [1, 3, 2, 4]
    assert report["local_search"]["queue_continuations"] == 1
    assert search.scores[original] == ((10,), True)


def test_queue_stops_before_a_trial_that_would_spend_validation_room():
    search = SimpleNamespace(deadline=20.0, clock=lambda: 18.4, full_decode_cost=lambda: 1.0,
                             trial_decode_cost=lambda: 0.7)
    budget = object.__new__(NeighborhoodBudget)
    budget.search, budget.seconds = search, 10.0
    budget.elapsed, budget.started_elapsed = lambda: 0.0, 0.0
    assert not budget.can_try()
    search.clock = lambda: 18.0
    assert budget.can_try()
    budget.elapsed = lambda: 9.5
    assert not budget.can_try()


def _stagnant_search(now, *, same_entry=False):
    reference = SimpleNamespace(order=(1, 2), decision_key=lambda: (1, 2))
    # A decoded pool entry with checkpoints is a ready reference: the restart needs no capture decode.
    alternate = SimpleNamespace(order=(2, 1), decision_key=lambda: (2, 1), decoded_order=True, checkpoints=[object()])
    selected = reference if same_entry else alternate
    best = {"score": (1,)}
    actions = []
    search = SimpleNamespace(clock=lambda: now[0], deadline=20.0, started=0.0,
                             limits=SimpleNamespace(stagnation_iterations=10), non_improving=0,
                             trial_decode_cost=lambda: 0.5, full_decode_cost=lambda: 1.0,
                             reference=reference, best=best, pool_rnd=None,
                             _seed_solution_pool=lambda: actions.append("seed"),
                             _activate_entry=lambda entry: actions.append(entry.order),
                             rotation=SimpleNamespace(reset_sizes=lambda: actions.append("reset")),
                             solution_pool=SimpleNamespace(pick=lambda *a, **k: selected),
                             report={"improvements": 0, "pool": {"restarts": 0}, "local_search": {
                                 "diversification_budget_pruned": 0, "diversification_requests": 0}})
    return search, reference, alternate, actions


def test_short_budget_can_switch_reference_before_ten_iterations():
    now = [0.0]
    search, original, alternate, actions = _stagnant_search(now)
    policy = BudgetStagnation(search)
    search.non_improving, now[0] = 2, 4.0
    assert policy.reference() is alternate
    assert actions == ["seed", (2, 1), "reset"]
    assert search.best == {"score": (1,)}
    assert search.report["pool"]["restarts"] == 1
    assert policy.consume_exploration() and not policy.consume_exploration()
    assert original.order == (1, 2)


def test_stagnation_preserves_reference_when_restart_cannot_be_used():
    now = [0.0]
    search, original, _, actions = _stagnant_search(now)
    policy = BudgetStagnation(search)
    search.non_improving, now[0] = 2, 18.5
    assert policy.reference() is original
    assert not actions and not policy.consume_exploration()
    assert search.report["local_search"]["diversification_budget_pruned"] == 1


def test_single_entry_pool_can_change_hint_without_faking_a_restart():
    now = [0.0]
    search, original, _, actions = _stagnant_search(now, same_entry=True)
    policy = BudgetStagnation(search)
    search.non_improving, now[0] = 2, 4.0
    assert policy.reference() is original
    assert policy.consume_exploration()
    assert actions == ["seed"] and search.report["pool"]["restarts"] == 0


def test_distant_insertion_probes_keep_hard_predecessors_and_successors():
    parent = SimpleNamespace(predecessors={3: {1}}, successors={3: {5}})
    positions = extended_positions([1, 2, 4, 5, 6], 3, [2], parent)
    assert positions == [2, 1, 3]
    for position in positions:
        order = [1, 2, 4, 5, 6]
        order.insert(position, 3)
        assert order.index(1) < order.index(3) < order.index(5)


def test_joint_window_construction_timeout_clears_the_local_budget(monkeypatch):
    search = SimpleNamespace(clock=lambda: 0.0, deadline=20.0, local_budget=None,
                             full_decode_cost=lambda: 1.0, trial_decode_cost=lambda: 0.5,
                             rotation=SimpleNamespace(selected=SimpleNamespace(name="resource_window")),
                             report={"iterations": 2, "local_search": {"neighborhoods": 0}})

    def exhausted(*args):
        assert search.local_budget is not None
        raise local._BudgetExhausted(local.LOCAL_BUDGET_REASON)

    monkeypatch.setattr(local, "joint_removed", exhausted)
    iteration = LargeIGIteration(search)
    with pytest.raises(local._BudgetExhausted, match=local.LOCAL_BUDGET_REASON):
        _finish(iteration._repair(SimpleNamespace(order=(1, 2, 3, 4)), (1, 2, 3)))
    assert search.local_budget is None


def test_feasible_partial_repair_leaves_opportunities_for_other_removed_operations():
    iteration = LargeIGIteration(SimpleNamespace())
    iteration.pending_insertions = 2
    reference = SimpleNamespace(score=(10,))
    assert iteration._position_finished(((12,), True), (12,), reference, False)
    assert not iteration._position_finished(None, (12,), reference, False)
    assert not iteration._position_finished(((12,), True), (12,), reference, True)
    iteration.pending_insertions = 0
    assert not iteration._position_finished(((12,), True), (12,), reference, False)
