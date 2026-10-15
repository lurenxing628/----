"""One clock verifies shared costs, useful target opportunities and stopping."""

import pytest

from core.services.scheduler.run.optimizer.shared_budget import SharedSearchBudget, SharedSearchSkip


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def test_shared_budget_admits_costs_rotates_useful_opportunities_and_requires_both_stall_limits():
    targets = ("min_overdue", "min_tardiness", "min_changeover")
    primary, auxiliary, changeover = targets

    def budget_at(clock, seconds):
        return SharedSearchBudget(clock=clock, started_at=clock(), deadline=clock() + seconds,
                                  target_objectives=targets, configured_seconds=seconds)

    def action(budget, clock, objective, seconds=0.1, **facts):
        clock.advance(seconds)
        budget.record_action(objective, "search", seconds, **facts)

    clock = _Clock()
    budget = budget_at(clock, 10.0)
    clock.advance(0.1)
    budget.charge_preparation(primary, "shared_preparation", 0.1)
    assert budget.select_goal(targets) == primary
    action(budget, clock, primary, 0.2, new_decisions=1, initial=True, first_complete=True)
    preparation = budget.summary()
    assert preparation["phase_elapsed_seconds"]["shared_preparation"] == pytest.approx(0.1)
    assert preparation["elapsed_seconds"] == pytest.approx(0.3)
    assert [preparation["objectives"][goal]["preparation_seconds"] for goal in targets] == [0.1, 0.0, 0.0]

    # Noop and cache consume time; the next target gets control and the useful
    # startup opportunity remains due for those two targets on the next round.
    assert budget.select_goal(targets) == primary
    action(budget, clock, primary, 0.001)
    assert not budget.has_minimum_opportunity(primary)
    assert budget.select_goal(targets) == auxiliary
    action(budget, clock, auxiliary, 0.001, reused_decisions=1)
    assert not budget.has_minimum_opportunity(auxiliary)
    assert budget.select_goal(targets) == changeover
    action(budget, clock, changeover, new_decisions=1)
    assert budget.select_goal(targets) == primary
    action(budget, clock, primary, new_decisions=1)
    assert budget.select_goal(targets) == auxiliary
    action(budget, clock, auxiliary, new_decisions=1)
    assert all(budget.has_minimum_opportunity(goal) for goal in targets)

    # Actual charged time and 60/20/20 weights select the still cheaper auxiliary.
    assert budget.select_goal(targets) == changeover
    action(budget, clock, changeover, new_decisions=1)
    assert budget.summary()["objective_status"][changeover] == "paused_no_gain"
    assert budget.select_goal(targets) == auxiliary
    action(budget, clock, auxiliary, new_decisions=1, improved_objectives=targets)
    opportunity = budget.summary()["objectives"][auxiliary]
    assert opportunity["improvement_action_count"] == 1
    assert opportunity["feedback_bonus"] == pytest.approx(0.25)
    assert opportunity["objective_status"] == "searched"
    assert budget.select_goal(targets) == primary

    clock = _Clock()
    yielding = budget_at(clock, 10.0)
    action(yielding, clock, primary, new_decisions=1, initial=True, first_complete=True)
    assert yielding.select_goal(targets) == primary
    action(yielding, clock, primary, 0.001)
    for goal in (auxiliary, changeover):
        assert yielding.select_goal(targets) == goal
        action(yielding, clock, goal, new_decisions=1)
    assert yielding.select_goal(targets) == primary
    action(yielding, clock, primary, 0.001)
    assert not yielding.has_minimum_opportunity(primary)
    assert yielding.select_goal(targets) == auxiliary

    # Admission uses a single initial free construction and the latest three
    # measured costs. A rejected expensive resume leaves a payable kind available.
    clock = _Clock()
    rejected = budget_at(clock, 10.0)
    with pytest.raises(SharedSearchSkip) as no_request:
        rejected.reject("estimated_decode_cost")
    assert no_request.value.reason == "estimated_decode_cost"
    assert no_request.value.request_id is None and no_request.value.receipt is None
    rejection = rejected.summary()
    assert rejection["admission_skips"] == {"estimated_decode_cost": 1}
    assert rejection["actual_decoder_count"] == 0
    assert all(not samples for samples in rejection["cost_samples"].values())

    costs = budget_at(clock, 10.0)
    with pytest.raises(SharedSearchSkip, match="estimated_decode_cost"):
        costs.require_decode("batch_order_full")
    assert costs.summary()["admission_skips"] == {"estimated_decode_cost": 1}
    costs.require_decode("batch_order_full", first_construction=True)
    with pytest.raises(SharedSearchSkip, match="estimated_decode_cost"):
        costs.require_decode("sgs_full", first_construction=True)
    assert costs.summary()["admission_skips"] == {"estimated_decode_cost": 2}
    assert costs.summary()["actual_decoder_count"] == 0
    clock.advance(0.4)
    costs.record_decode("batch_order_full", 0.4)
    costs.record_action(primary, "initial", 0.4, new_decisions=1, initial=True, first_complete=True)

    def decode(kind, seconds, **admission):
        costs.require_decode(kind, **admission)
        clock.advance(seconds)
        costs.record_decode(kind, seconds)

    assert costs.estimate("sgs_resume") == pytest.approx(0.5)
    for seconds in (0.8, 0.2, 0.3):
        decode("batch_order_full", seconds)
    assert costs.estimate("batch_order_full") == pytest.approx(1.0)
    decode("batch_order_full", 0.1)
    assert costs.estimate("batch_order_full") == pytest.approx(0.375)
    assert costs.estimate("sgs_full") == pytest.approx(0.375)
    decode("sgs_full", 1.0)
    decode("sgs_resume", 0.2, reserve_full=True)
    decode("sgs_full", 0.1)
    assert costs.estimate("sgs_resume") == pytest.approx(0.25)
    assert costs.estimate("sgs_full") == pytest.approx(1.25)
    clock.advance(5.5)
    assert costs.remaining() == pytest.approx(1.4)
    assert costs.select_goal(targets) == primary
    with pytest.raises(SharedSearchSkip) as refused:
        costs.require_decode("sgs_resume", reserve_full=True)
    assert refused.value.reason == "estimated_decode_cost"
    costs.record_action(primary, "resume", 0.0, skip_reason=refused.value.reason)
    assert costs.select_goal(targets) == auxiliary
    decode("batch_order_full", 0.05)
    costs.record_action(auxiliary, "search", 0.05, new_decisions=1)

    # A failed capture has a real cost. Its plain-full retry rereads the clock
    # and cannot start after that non-preempted call has consumed the deadline.
    decode("sgs_full", 1.5)
    with pytest.raises(SharedSearchSkip) as retry:
        costs.require_decode("sgs_full")
    assert retry.value.reason == "time_budget"
    measured = costs.summary()
    assert measured["actual_decoder_count"] == 10
    assert measured["deadline_overrun_seconds"] == pytest.approx(0.15)
    assert measured["stop_reason"] == "time_budget"

    # Short and long runs differ only in the specified probe/stall thresholds.
    # Initial completion and later strict progress each reset stagnation.
    for seconds, probe_limit, decision_limit, stall_seconds in ((10.0, 2, 6, 2.0), (30.0, 4, 10, 5.0)):
        clock = _Clock()
        stalled = budget_at(clock, seconds)
        action(stalled, clock, primary, 0.1, new_decisions=1, initial=True)
        assert stalled.select_goal(targets) == primary
        clock.advance(0.9)
        stalled.record_action(primary, "initial", 0.0, initial=True, first_complete=True)
        assert stalled.summary()["last_improvement_elapsed_seconds"] == pytest.approx(1.0)
        assert stalled.summary()["stalled_new_decisions"] == 0
        for goal in targets:
            assert stalled.select_goal(targets) == goal
            action(stalled, clock, goal, 0.01, new_decisions=1)
        for _ in range(probe_limit - 1):
            action(stalled, clock, auxiliary, 0.01, new_decisions=1)
            action(stalled, clock, changeover, 0.01, new_decisions=1)
        assert stalled.summary()["objective_status"][auxiliary] == "paused_no_gain"
        assert stalled.summary()["objective_status"][changeover] == "paused_no_gain"
        assert stalled.select_goal(targets) == primary
        assert stalled.summary()["stalled_new_decisions"] == decision_limit - 1
        action(stalled, clock, primary, 0.01, new_decisions=1)
        assert stalled.should_stop() is None  # Count alone is insufficient.
        clock.advance(stall_seconds)
        assert stalled.should_stop() == "stagnation"

        action(stalled, clock, primary, 0.01, new_decisions=1, improved_objectives=(changeover,))
        assert stalled.summary()["stalled_new_decisions"] == 0
        assert stalled.should_stop() is None
        clock.advance(stall_seconds)
        assert stalled.should_stop() is None  # Time alone is insufficient.
        action(stalled, clock, primary, 0.01, reused_decisions=1)
        action(stalled, clock, primary, 0.01)  # Necessary reconstruction / noop.
        assert stalled.summary()["stalled_new_decisions"] == 0
        for _ in range(decision_limit - 1):
            action(stalled, clock, primary, 0.01, new_decisions=1)
        assert stalled.should_stop() is None
        action(stalled, clock, primary, 0.01, new_decisions=1)
        assert stalled.should_stop() == "stagnation"
