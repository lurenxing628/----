"""真实候选比较搜索规则池并公开实际采用的规则。"""

import itertools

import pytest

from core.algorithm_contracts.dispatch_rules import dispatch_rule_search_pool
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_candidate_summary import (
    candidate_comparison_public_summary,
    candidate_public_summary,
)
from tests._support.optimizer_business_cases import case_environment, fixture_data

# Registry rules plus the ATC k ladder; the optimizer may adopt any token from this pool.
RULE_POOL = set(dispatch_rule_search_pool(("slack", "cr", "atc")))


def _compare(scenario, objective="min_overdue"):
    config = {"seed": 0, "time_budget_seconds": 2, "run_time_budget_seconds": 20.0}
    ticks = itertools.count(0.0, 0.01)
    data = fixture_data(scenario)
    with case_environment(data, objective, config) as schedule_input:
        return run_candidate_comparison(
            schedule_input=schedule_input, clock=lambda: next(ticks), run_time_budget_seconds=config["run_time_budget_seconds"],
            weight_count=3, selection_policy="score_only", strict_mode=True,
        )


@pytest.fixture(scope="module")
def shift_pool_outcome():
    return _compare("shift_pool")


def test_baseline_candidate_starts_from_every_rule_and_the_rule_neighborhood_really_moves(shift_pool_outcome):
    baseline = next(plan for plan in shift_pool_outcome.candidates if plan.candidate_key == "baseline")
    assert baseline.status == "completed"
    efficiency = baseline.search_report["candidate_profile"]["multi_start_efficiency"]
    assert efficiency["configured_candidates"] == len(RULE_POOL) and efficiency["decoded_candidates"] == len(RULE_POOL)
    neighborhood = baseline.search_report["neighborhood_summary"]["sgs_dispatch_rule"]
    assert neighborhood["effective"] > 0
    assert neighborhood["noop"] < neighborhood["attempted"]


def test_adopted_rule_is_reported_and_may_differ_from_the_configured_rule(shift_pool_outcome):
    for plan in shift_pool_outcome.candidates:
        assert plan.status == "completed"
        assert plan.dispatch_mode == "sgs" and plan.dispatch_rule == "slack"
        assert plan.adopted_dispatch_rule in RULE_POOL
        public = candidate_public_summary(plan)
        assert public["adopted_dispatch_rule"] == plan.adopted_dispatch_rule
        assert ("configured_dispatch_rule" in public) is (plan.adopted_dispatch_rule != plan.dispatch_rule)
    baseline = next(plan for plan in shift_pool_outcome.candidates if plan.candidate_key == "baseline")
    # Measured under the fixed clock: the configured slack start loses to a ladder atc on this fixture.
    assert baseline.adopted_dispatch_rule == "atc:k=16.0"
    assert candidate_public_summary(baseline)["configured_dispatch_rule"] == "slack"
    summary = candidate_comparison_public_summary(shift_pool_outcome)
    assert [row["adopted_dispatch_rule"] for row in summary["candidates"]] == [plan.adopted_dispatch_rule for plan in shift_pool_outcome.candidates]
