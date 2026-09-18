"""IG reference solutions: capture accounting, start fallback, adoption rollback and decode admission labels."""
from __future__ import annotations

from dataclasses import replace

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy import _BudgetExhausted, admit_parent_decode
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_contract import (
    IteratedGreedyLimits,
    iterated_greedy_public_message,
    new_iterated_greedy_report,
)
from core.services.scheduler.run.optimizer_graph_ready_iterated_greedy_incumbent import incumbent_events
from tests._support.optimizer_graph_ready_benchmark import BASE_BATCH_ORDER
from tests._support.optimizer_graph_ready_ig_harness import IGHarness


def test_start_capture_reproducing_the_parent_is_a_reference_capture_not_a_rejection():
    harness = IGHarness(flexible=True)
    harness.search._start_reference()
    report = harness.report
    assert report["reference_basis"] == "parent_order" and report["parent_order_consistent"] is True
    assert report["parent_order_score"] == report["parent_score"] == list(harness.baseline["score"])
    assert report["reference_captures"] == 1 and report["reference_capture_divergences"] == 0
    assert report["rejected_by_reason"] == {} and report["improvements"] == 0
    assert incumbent_events(report) == 0 and harness.state.evaluated_candidates == 2, "the capture is real decode work"
    harness.assert_initial_incumbent()


def test_divergent_capture_is_counted_apart_and_marks_the_parent_order_inconsistent(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_iterated_greedy_moves as moves

    harness = IGHarness()
    # A parent order that is not the parent's own (its decoded start-time order): its capture yields another schedule.
    monkeypatch.setattr(moves, "decoded_topological_order", lambda rows, predecessors: (1, 2, 4, 3))
    harness.search._start_reference()
    report = harness.report
    assert report["reference_basis"] == "parent_order" and report["parent_order_consistent"] is False
    assert report["reference_captures"] == 0 and report["reference_capture_divergences"] == 1
    assert report["reference_capture_improvements"] == 0 and report["improvements"] == 0
    assert harness.search.reference is not None and harness.search.reference.order == (1, 2, 4, 3)


def test_start_falls_back_to_the_next_pool_entry_when_the_first_capture_is_rejected():
    harness = IGHarness(flexible=True, strict_mode=False)
    other = harness.candidate((1, 2, 4, 3), overrides=harness.overrides("M2", "P2"))
    harness.pool.elites.append({"candidate": other, "profile": harness.profile})
    refused = []

    def refuse_first(kwargs):
        if not refused:
            refused.append(tuple(kwargs["repair_decision"].operation_order))
            raise ValidationError("controlled capture failure", field="controlled", details={"reason": "controlled_failure"})

    harness.before_evaluate = refuse_first
    harness.search._start_reference()
    reference = harness.search.reference
    assert reference is not None and reference.decoded_order
    assert harness.report["pool"]["start_captures_failed"] == 1 and harness.report["pool"]["initial_entries"] == 2
    assert harness.report["reference_basis"] == "parent_order" and harness.report["parent_order_consistent"] is True
    assert harness.report["rejected_by_reason"] == {"controlled_failure": 1}
    assert harness.search.parent.order == reference.order and harness.search.parent.inherited == reference.resource_overrides
    assert (reference.order, reference.resource_overrides) != (refused[0], None)


def test_start_without_any_capturable_entry_reports_parent_order_rejected():
    harness = IGHarness(strict_mode=False)

    def refuse(kwargs):
        raise ValidationError("controlled capture failure", field="controlled", details={"reason": "controlled_failure"})

    harness.before_evaluate = refuse
    with pytest.raises(_BudgetExhausted) as excinfo:
        harness.search._start_reference()
    assert excinfo.value.reason == "parent_order_rejected"
    assert harness.report["pool"]["start_captures_failed"] == 1 and harness.search.reference is None


def test_adoption_whose_capture_cannot_start_rolls_back_to_the_previous_walk_context():
    harness = IGHarness(flexible=True)
    reference = harness.start()
    new_batch_order = tuple(reversed(BASE_BATCH_ORDER))
    incoming = harness.candidate((4, 3, 2, 1), overrides=harness.overrides("M2", "P2"), batch_order=new_batch_order)
    harness.state.mark_candidate_accepted(incoming, origin="graph_ready_v2_repaired")
    harness.search.limits = replace(harness.search.limits, max_decodes=harness.report["decodes"])
    with pytest.raises(_BudgetExhausted) as excinfo:
        harness.search.adopt_incumbent(incoming, harness.other_profile)
    assert excinfo.value.reason == "decode_budget"
    assert harness.search.best is incoming, "the improved incumbent is adopted even when the walk cannot follow it"
    assert harness.search.parent.batch_order == tuple(BASE_BATCH_ORDER) and harness.search.reference is reference
    assert harness.report["incumbent_adoptions"] == 1 and harness.report["incumbent_adoption_rollbacks"] == 1
    # The restored context still matches the reference's checkpoints: a resumed trial runs, nothing mismatches.
    harness.search.limits = replace(harness.search.limits, max_decodes=100)
    harness.schedule_calls.clear()
    assert harness.search._score_trial((1, 3, 4, 2), reference) is not None
    assert harness.schedule_calls[0].get("decode_resume") is not None
    assert harness.search.checkpoints.disabled_reason is None


def test_adoption_whose_capture_is_rejected_rolls_back_without_raising():
    harness = IGHarness(flexible=True, strict_mode=False)
    reference = harness.start()
    new_batch_order = tuple(reversed(BASE_BATCH_ORDER))
    incoming = harness.candidate((4, 3, 2, 1), overrides=harness.overrides("M2", "P2"), batch_order=new_batch_order)

    def refuse_new_context(kwargs):
        if tuple(kwargs["repair_decision"].batch_order) == new_batch_order:
            raise ValidationError("controlled capture failure", field="controlled", details={"reason": "controlled_failure"})

    harness.before_evaluate = refuse_new_context
    harness.search.adopt_incumbent(incoming, harness.other_profile)
    assert harness.search.best is incoming
    assert harness.report["incumbent_adoption_rollbacks"] == 1 and harness.report["rejected_by_reason"] == {"controlled_failure": 1}
    assert harness.search.parent.batch_order == tuple(BASE_BATCH_ORDER) and harness.search.reference is reference
    harness.before_evaluate = None
    harness.schedule_calls.clear()
    assert harness.search._score_trial((1, 3, 4, 2), reference) is not None
    assert harness.schedule_calls[0].get("decode_resume") is not None


def test_parent_decode_that_cannot_fit_the_remaining_time_is_reported_as_decode_would_overrun():
    report = new_iterated_greedy_report(IteratedGreedyLimits(), objective_name="min_overdue")
    best = {"runtime_ms": 500.0, "score": (0.0, 1.0)}
    with pytest.raises(_BudgetExhausted) as excinfo:
        admit_parent_decode(best, clock=lambda: 10.0, deadline=10.3, report=report)
    assert excinfo.value.reason == "decode_would_overrun"
    admission = report["decode_admission"]
    assert admission["policy"] == "observed_parent_candidate_runtime"
    assert admission["estimated_decode_ms"] == 500.0 and admission["remaining_ms"] == pytest.approx(300.0)
    with pytest.raises(_BudgetExhausted) as excinfo:
        admit_parent_decode(best, clock=lambda: 10.3, deadline=10.3, report=report)
    assert excinfo.value.reason == "time_budget"
    admit_parent_decode(best, clock=lambda: 10.0, deadline=11.0, report=report)
    report.update(status="skipped_by_budget", stop_reason="decode_would_overrun")
    assert "预计一次完整解码放不进剩余预算" in iterated_greedy_public_message(report)
    report.update(stop_reason="decode_budget")
    assert "解码次数上限已用完" in iterated_greedy_public_message(report)


def test_run_that_admits_no_decode_never_claims_the_time_budget_ran_out():
    harness = IGHarness()
    harness.baseline["runtime_ms"] = 200000.0  # 200 s of parent decode against a 100 s deadline
    harness.schedule_calls.clear()
    assert harness.search.run(harness.baseline) is harness.baseline
    report = harness.report
    assert report["decodes"] == 0 and report["status"] == "skipped_by_budget"
    assert report["stop_reason"] == "decode_would_overrun" and report["decode_admission"]["remaining_ms"] == pytest.approx(100000.0)
    assert harness.schedule_calls == [] and harness.search.reference is None
