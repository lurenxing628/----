"""Constructive starts remain proposals until ordinary SGS validates their complete score."""
from dataclasses import replace

import pytest

from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy import _BudgetExhausted, _parent_from_candidate
from tests.algorithm.test_graph_ready_ig_incumbent_context_contract import _Harness


def _enabled_harness():
    harness = _Harness()
    harness.search.limits = replace(harness.search.limits, due_date_seed=True)
    harness.report["initial_seed"]["enabled"] = True
    harness.schedule_calls.clear()
    return harness


def test_due_date_start_is_formally_decoded_before_becoming_the_reference():
    harness = _enabled_harness()
    harness.search._start_reference()
    seed = harness.report["initial_seed"]
    assert seed["status"] == "used_as_reference" and seed["requires_sgs_validation"]
    assert seed["selected"] and seed["incumbent_improved"]
    assert seed["validated_score"] == list(harness.search.best["score"])
    assert tuple(harness.search.best["score"]) < tuple(harness.baseline["score"])
    assert seed["decodes"] == len(harness.schedule_calls) == 1
    assert harness.schedule_calls[0].get("decode_resume") is None
    assert harness.schedule_calls[0].get("decode_checkpoints") is not None
    assert harness.search.reference.candidate is harness.search.best


def _pretend_proposal(order):
    return {"order": order, "status": "proposed", "reason": None, "estimated_key": (0, 0),
            "original_estimated_key": (10, 10), "probes": 1, "construction_stop": "complete"}


def test_optimistic_model_cannot_replace_a_better_validated_start(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_seed as seed_module

    harness = _enabled_harness()
    good = harness.candidate((1, 3, 4, 2))
    assert tuple(good["score"]) < tuple(harness.baseline["score"])
    harness.search.best = good
    harness.state.mark_candidate_accepted(good, origin=good["candidate_origin"])
    harness.search._set_parent(_parent_from_candidate(good, operations=harness.operations,
                                                     graph_context=harness.context), harness.profile)
    accepted = harness.state.accepted_candidates
    monkeypatch.setattr(seed_module, "build_due_date_seed", lambda **kwargs: _pretend_proposal((1, 2, 3, 4)))
    harness.schedule_calls.clear()
    harness.search._start_reference()
    seed = harness.report["initial_seed"]
    assert seed["status"] == "rejected" and seed["reason"] == "worse_than_source"
    assert not seed["selected"] and not seed["incumbent_improved"]
    assert len(harness.schedule_calls) == 2 and seed["decodes"] == 1
    assert tuple(harness.search.reference.score) == tuple(good["score"])
    assert harness.search.best is good and harness.state.accepted_candidates == accepted


def test_time_exhausted_during_construction_does_not_publish_its_estimate(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_seed as seed_module

    harness = _enabled_harness()

    def out_of_time(**kwargs):
        harness.now = harness.search.deadline
        return _pretend_proposal((1, 3, 4, 2))

    monkeypatch.setattr(seed_module, "build_due_date_seed", out_of_time)
    with pytest.raises(_BudgetExhausted) as exc:
        harness.search._start_reference()
    assert exc.value.reason == "time_budget"
    assert harness.report["initial_seed"]["status"] == "skipped_by_budget"
    assert harness.report["initial_seed"]["decodes"] == 0 and harness.schedule_calls == []
    harness.assert_initial_incumbent()


def test_other_objectives_keep_the_existing_pool_start(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_seed as seed_module

    harness = _enabled_harness()
    harness.report["objective_name"] = "min_tardiness"

    def forbidden(**kwargs):
        raise AssertionError("min_overdue construction must not run for another objective")

    monkeypatch.setattr(seed_module, "build_due_date_seed", forbidden)
    harness.search._start_reference()
    assert harness.report["initial_seed"]["status"] == "not_applicable"
    assert len(harness.schedule_calls) == 1
    harness.assert_initial_incumbent()
