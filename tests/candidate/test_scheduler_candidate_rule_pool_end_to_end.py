"""完整规则池与实际共享规则动作保留真实采用来源。"""

import itertools

import pytest

from core.models.schedule_config_runtime_fields import default_snapshot_values
from core.models.schedule_config_runtime_snapshot import snapshot_from_values
from core.services.scheduler.config.config_field_spec import choices_for
from core.services.scheduler.run import schedule_candidate_runner
from core.services.scheduler.run.optimizer.multi_start import _iter_multi_start_specs
from core.services.scheduler.run.schedule_candidate_runner import run_candidate_comparison
from core.services.scheduler.run.schedule_candidate_summary import (
    candidate_comparison_public_summary,
    candidate_public_summary,
)
from tests._support.optimizer_business_cases import case_environment, fixture_data

# Independent token contract; a limited shared run can execute a subset.
RULE_POOL = {"slack", "cr", "atc", "atc:k=0.5", "atc:k=1.0", "atc:k=4.0", "atc:k=8.0", "atc:k=16.0"}


def _compare(scenario, objective="min_overdue"):
    config = {"seed": 0, "time_budget_seconds": 2, "run_time_budget_seconds": 20.0}
    ticks = itertools.count(0.0, 0.01)
    data = fixture_data(scenario)
    with case_environment(data, objective, config) as schedule_input, pytest.MonkeyPatch.context() as runner_patch:
        runner_patch.setattr(schedule_candidate_runner, "monotonic", lambda: next(ticks))
        return run_candidate_comparison(
            schedule_input=schedule_input, run_time_budget_seconds=config["run_time_budget_seconds"], strict_mode=True,
        )


@pytest.fixture(scope="module")
def shift_pool_outcome():
    return _compare("shift_pool")


def test_complete_rule_pool_and_actual_shared_rule_actions(shift_pool_outcome, record_property):
    values = default_snapshot_values()
    values.update(sort_strategy="fifo", dispatch_mode="sgs", dispatch_rule="slack")
    specs = list(_iter_multi_start_specs(
        keys=["fifo"], dispatch_modes=["sgs"], dispatch_rule_cfg="slack",
        valid_dispatch_rules=list(choices_for("dispatch_rule")), snapshot=snapshot_from_values(values),
        deadline_reached=lambda: False,
    ))
    generated_rules = [spec[2] for spec in specs]
    record_property("generated_dispatch_rules", generated_rules)
    assert len(generated_rules) == len(set(generated_rules)) == 8
    assert set(generated_rules) == RULE_POOL
    assert generated_rules[0] == "slack"

    events = shift_pool_outcome.unified_process["events"]
    requests = [event for event in events if event["event_type"] in ("new_decision", "decision_reused")]
    requested_rules = {event["dispatch_rule"] for event in requests}
    multi_start = [event for event in requests if event["phase"] == "multi_start"]
    skipped = [{"dispatch_rule": event.get("dispatch_rule"), "reason": event.get("reason")}
               for event in events if event["event_type"] == "decode_skipped"]
    proposed_rules = {event["dispatch_rule"] for event in events
                      if event.get("request_id") is not None and event.get("dispatch_rule") in RULE_POOL}
    record_property("shared_dispatch_rules", sorted(requested_rules))
    record_property("multi_start_dispatch_rules", sorted({event["dispatch_rule"] for event in multi_start}))
    record_property("decode_skipped", skipped)
    record_property("not_proposed_dispatch_rules", sorted(RULE_POOL - proposed_rules))
    assert requested_rules and requested_rules <= RULE_POOL
    assert any(event["dispatch_rule"] == "atc:k=16.0" for event in requests)
    assert requests[0]["phase"] == "multi_start"
    observations = [event for event in events if event["event_type"] == "archive_observation" and event["verified"]]
    rules_by_entry = {}
    for event in observations:
        rules_by_entry.setdefault(event["entry_id"], event["dispatch_rule"])
        assert isinstance(event["elapsed_ms"], int) and event["elapsed_ms"] >= 0
    rule_moves = [event for event in requests if event["phase"] == "local_search"
                  and event["dispatch_mode"] == "sgs" and event["parent_entry_id"] in rules_by_entry
                  and event["dispatch_rule"] != rules_by_entry[event["parent_entry_id"]]]
    record_property("effective_rule_move_count", len(rule_moves))
    assert rule_moves
    assert all(event["dispatch_rule"] in RULE_POOL for event in rule_moves)
    non_improving = [event for event in observations if not event["content_reused"]
                     and not event["improved_objectives"] and not event["initialized_objectives"]]
    record_property("non_improving_observation_count", len(non_improving))
    assert non_improving


def test_adopted_rule_and_origin_match_the_actual_shared_source(shift_pool_outcome):
    events = {event["event_id"]: event for event in shift_pool_outcome.unified_process["events"]}
    for plan in shift_pool_outcome.candidates:
        assert plan.status == "completed"
        assert plan.dispatch_mode == "sgs"
        assert plan.adopted_dispatch_rule in RULE_POOL
        source = events[plan.search_evidence_ref["source_event_id"]]
        assert source["event_type"] == "archive_observation" and source["verified"] is True
        assert plan.adopted_dispatch_rule == source["dispatch_rule"] == plan.origin["dispatch_rule"]
        assert plan.origin["origin"] == source["origin"]
        assert plan.origin["search_objective"] == source["search_objective"]
        public = candidate_public_summary(plan)
        assert public["adopted_dispatch_rule"] == plan.adopted_dispatch_rule
        assert public["origin"] == plan.origin
    assert any(plan.adopted_dispatch_rule != "slack" for plan in shift_pool_outcome.candidates)
    summary = candidate_comparison_public_summary(shift_pool_outcome)
    assert [row["adopted_dispatch_rule"] for row in summary["candidates"]] == [plan.adopted_dispatch_rule for plan in shift_pool_outcome.candidates]
