"""Shared budgets include construction time and stop new decodes at equality."""

from unittest.mock import Mock

import pytest

from core.services.scheduler.run import optimizer_local_search_round as local_round
from core.services.scheduler.run.optimizer_deadline_guard import (
    can_afford_decode,
    guard_decoder,
    observed_decode_seconds,
)
from core.services.scheduler.run.optimizer_grasp_ig_candidates import _deadline_reached
from core.services.scheduler.run.optimizer_local_search import _local_search_stop_reason
from core.services.scheduler.run.optimizer_search_budget import SearchBudgetExhausted
from tests.algorithm import test_optimizer_vns_sa_local_search_contract as local_cases


@pytest.mark.parametrize("instant", [5.0, 5.001])
def test_exhausted_budget_does_not_start_another_local_or_constructive_round(instant):
    report = Mock()
    assert _deadline_reached(lambda: instant, 5.0, report)
    assert _local_search_stop_reason(now_value=instant, deadline=5.0, iteration=0, iteration_limit=10) == "time_budget"
    report.mark_deadline_reached.assert_called_once_with()


def test_decoder_started_in_time_may_finish_after_deadline():
    now = [4.0]
    report = Mock()

    def decode(value):
        now[0] = 7.0
        return value

    schedule = guard_decoder(decode, clock=lambda: now[0], deadline=5.0, search_report_state=report)
    assert schedule("real-result") == "real-result"
    with pytest.raises(SearchBudgetExhausted):
        schedule("must-not-run")
    report.mark_deadline_reached.assert_called_once_with()


def test_local_neighbor_construction_consumes_the_remaining_budget(monkeypatch):
    now = [1000.0]
    monkeypatch.setattr(local_cases, "_Clock", lambda **_kwargs: lambda: now[0])
    original = local_round.choose_neighborhood_move

    def expensive_move(**kwargs):
        move = original(**kwargs)
        now[0] = 1001.0
        return move

    monkeypatch.setattr(local_round, "choose_neighborhood_move", expensive_move)
    decode = Mock(side_effect=AssertionError("Decoder must not start after constructing the neighbor"))
    best = local_cases._candidate_three_batches()
    returned, report = local_cases._run_local_search_once(best=best, acceptance="improve_only", schedule_fn=decode)
    assert returned is best
    decode.assert_not_called()
    assert report["stop_reason"] == "time_budget"
    assert report["best_improved_candidates"] == 0


def test_decoder_error_is_not_converted_to_a_budget_skip():
    def fail():
        raise ValueError("real decoder error")

    schedule = guard_decoder(fail, clock=lambda: 1.0, deadline=5.0, search_report_state=None)
    with pytest.raises(ValueError, match="real decoder error"):
        schedule()


def test_known_decode_cost_reserves_time_without_claiming_the_clock_expired():
    report, decode = Mock(), Mock(return_value="full-result")
    best = {"initial_decode_runtime_ms": 2000.0}
    assert not can_afford_decode(best, clock=lambda: 3.1, deadline=5.0, search_report_state=report, phase="local_search")
    report.mark_phase_skipped.assert_called_once_with("local_search", "estimated_decode_cost")
    report.mark_deadline_reached.assert_not_called()
    schedule = guard_decoder(decode, clock=lambda: 3.1, deadline=5.0, search_report_state=report,
                              minimum_decode_seconds=observed_decode_seconds(best))
    with pytest.raises(SearchBudgetExhausted, match="estimated_decode_cost"):
        schedule()
    decode.assert_not_called()
    exact = guard_decoder(decode, clock=lambda: 3.0, deadline=5.0, search_report_state=report, minimum_decode_seconds=2.0)
    assert exact() == "full-result"


@pytest.mark.parametrize("cost", [-1, float("nan"), float("inf"), True, "slow"])
def test_invalid_observed_cost_is_not_silently_used_as_a_budget(cost):
    with pytest.raises(ValueError):
        observed_decode_seconds({"initial_decode_runtime_ms": cost})
