"""Shortlist cost is advisory; local exhaustion preserves the incumbent and permits another task."""
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_contract import _BudgetExhausted
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_local import (
    LOCAL_BUDGET_REASON,
    NeighborhoodBudget,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_neighborhoods import build_generators
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_run import IteratedGreedyRun
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_screen import InsertionScreen
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_tail import trial_request


def test_screen_prioritizes_an_urgent_short_job_without_publishing_its_estimate():
    start = datetime(2026, 1, 5)
    rows = [SimpleNamespace(op_id=i, batch_id=str(i), machine_id="M", operator_id="O", op_type_name="T",
                            start_time=start, end_time=start + timedelta(hours=hours)) for i, hours in ((1, 8), (2, 1), (3, 2))]
    report = {"objective_name": "min_overdue", "duplicate_decision_pruned": 0,
              "local_search": {"screened_positions": 0, "shortlisted_positions": 0}}
    incumbent = {"results": rows, "score": (0, 1)}
    search = SimpleNamespace(parent=SimpleNamespace(predecessors={1: set(), 2: set(), 3: set()}),
                             metrics={1: {"due_deadline_hours": 30}, 2: {"due_deadline_hours": 2},
                                      3: {"due_deadline_hours": 30}}, report=report, scores={},
                             best=incumbent, _require_budget=lambda: None)
    screen = InsertionScreen(search, SimpleNamespace(candidate=incumbent, order=(1, 2, 3)))
    assert screen.select([1, 3], 2, [1, 0, 2], anchor=1, limit=1) == [0]
    assert search.best is incumbent and search.scores == {}
    assert report["local_search"] == {"screened_positions": 3, "shortlisted_positions": 1}


def test_local_time_counts_own_work_and_leaves_a_full_validation_reserve():
    now, own_time = [0.0], [0.0]

    def global_check():
        if now[0] >= 20:
            raise _BudgetExhausted("time_budget")

    search = SimpleNamespace(deadline=20.0, clock=lambda: now[0], full_decode_cost=lambda: 2.0,
                             trial_decode_cost=lambda: 2.0, _hard_budget_now=global_check, report={"iterations": 0})
    budget = NeighborhoodBudget(search, lambda: own_time[0], 3)
    assert budget.size == 1
    now[0] = 8.0  # Other stages used time, but this neighbourhood did no work.
    budget.check()
    own_time[0] = budget.seconds
    with pytest.raises(_BudgetExhausted, match=LOCAL_BUDGET_REASON):
        budget.check()
    now[0] = 20.0
    with pytest.raises(_BudgetExhausted, match="time_budget"):
        budget.check()


def test_local_exhaustion_does_not_stop_the_whole_stage():
    incumbent = {"score": (0, 5)}
    run = IteratedGreedyRun.__new__(IteratedGreedyRun)
    run.search = SimpleNamespace(best=incumbent)
    run.state = SimpleNamespace(best=incumbent)
    run.report = {"local_search": {"local_timeouts": 0}, "stop_reason": None}
    run.stopped, run.task_seconds = False, 0.0
    run.clock = lambda: 1.0
    run.iteration = object()

    def exhausted():
        raise _BudgetExhausted(LOCAL_BUDGET_REASON)

    run._advance = exhausted
    run.step()
    assert not run.stopped and run.iteration is None
    assert run.state.best is incumbent and run.report["local_search"]["local_timeouts"] == 1
    completed = []
    run._advance = lambda: completed.append(True)
    run.step()
    assert completed == [True] and run.state.best is incumbent


def test_each_new_trial_rearms_the_in_decode_budget_check():
    budget = SimpleNamespace(last_pick_check=6000, check_pick=lambda position: None)
    reference = SimpleNamespace(order=(1, 2, 3), checkpoints=[])
    request = trial_request(reference, resume=None, budget=budget)
    assert budget.last_pick_check == 0 and request.check_budget is budget.check_pick


def test_large_feedback_separates_task_completion_from_solution_quality():
    generator = build_generators(("time_window",), initial_size=3, max_size=6)[0]
    generator.completion_feedback = True
    initial = generator.difficulty.value
    generator.record(0.2, improved=False, fully_solved=True, idle=False, worse=True)
    assert generator.difficulty.value > initial and not generator.last_improved
    grown = generator.difficulty.value
    generator.record(0.2, improved=False, fully_solved=False, idle=False)
    assert generator.difficulty.value < grown


def test_no_new_neighbourhood_starts_without_trial_and_validation_room():
    search = SimpleNamespace(deadline=20.0, clock=lambda: 18.0, full_decode_cost=lambda: 1.7,
                             trial_decode_cost=lambda: 0.7, report={"iterations": 2, "local_search": {"validation_room_pruned": 0}})
    with pytest.raises(_BudgetExhausted, match="decode_would_overrun"):
        NeighborhoodBudget(search, lambda: 0.0, 3)
    assert search.report["local_search"]["validation_room_pruned"] == 1
    assert search.report["local_search"]["end_budget"]["remaining_ms"] == 2000
