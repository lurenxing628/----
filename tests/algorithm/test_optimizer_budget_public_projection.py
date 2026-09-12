"""Show the assigned slice while keeping detailed budget diagnostics bounded."""

import pytest

from core.services.scheduler.contracts.optimizer_public_search_report import project_search_report
from core.services.scheduler.summary.optimizer_public_summary import project_public_algo_summary


def _report(assigned=1250):
    return {"candidate_profile": {
        "configured_time_budget_seconds": 5,
        "assigned_time_budget_ms": assigned,
        "optimizer_budget": {
            "assigned_time_budget_ms": assigned,
            "preparation_runtime_ms": 45,
            "optimizer_time_budget_ms": 1205,
            "deadline_overrun_ms": 12,
            "policy": "shared_deadline_remaining_equal_slices_v1",
            "clock": "shared_monotonic",
            "candidate_id": "private-candidate",
            "raw_results": ["private-result"],
        },
    }}


def test_assigned_milliseconds_survive_public_projection_without_private_trace():
    public, diagnostics = project_search_report(_report())
    assert public["profile_public"] == {"configured_time_budget_seconds": 5, "assigned_time_budget_ms": 1250}
    budget = diagnostics["profile_diagnostics"]["optimizer_budget"]
    assert budget["preparation_runtime_ms"] == 45
    assert budget["deadline_overrun_ms"] == 12
    assert "candidate_id" not in budget and "raw_results" not in budget
    assert "optimizer_budget" not in public["profile_public"]
    algo, _ = project_public_algo_summary({"search_report": _report()})
    assert algo["search_report"]["profile_public"]["assigned_time_budget_ms"] == 1250


@pytest.mark.parametrize("invalid", [-1, float("inf"), float("nan"), "not-a-number", {}])
def test_invalid_assigned_budget_is_not_published(invalid):
    public, diagnostics = project_search_report(_report(invalid))
    assert "assigned_time_budget_ms" not in public["profile_public"]
    assert "assigned_time_budget_ms" not in diagnostics["profile_diagnostics"]["optimizer_budget"]


def test_allocation_feedback_diagnostics_keep_only_bounded_scalars():
    report = _report()
    expected = {
        "policy": "observed_strict_improvement_per_second_v1",
        "reason": "observed_strict_improvement_bonus",
        "observed_completed_count": 2, "observed_improvement_count": 1,
        "feedback_applied": True, "allocation_factor": 1.5,
        "equal_slice_ms": 1000, "minimum_untried_share_ms": 500,
        "reserved_for_other_candidates_ms": 1500, "candidate_sequence": 2,
        "strict_improvement": True, "elapsed_seconds": 1.0, "improvements_per_second": 1.0,
    }
    report["candidate_profile"]["optimizer_budget"]["allocation_feedback"] = {
        **expected, "score": [0, 1, 2], "history": [{"private_id": "candidate-123"}],
    }
    public, diagnostics = project_search_report(report)
    assert "allocation_feedback" not in public["profile_public"]
    assert diagnostics["profile_diagnostics"]["optimizer_budget"]["allocation_feedback"] == expected


@pytest.mark.parametrize("invalid", [-1, float("inf"), float("nan"), True, "1.5", {}, 10 ** 500])
def test_invalid_feedback_numbers_and_unknown_labels_do_not_escape(invalid):
    report = _report()
    report["candidate_profile"]["optimizer_budget"]["allocation_feedback"] = {
        "allocation_factor": invalid, "elapsed_seconds": invalid, "improvements_per_second": invalid,
        "policy": "private policy", "reason": {"raw_result": "private"},
        "strict_improvement": "yes", "feedback_applied": "false",
    }
    _, diagnostics = project_search_report(report)
    assert "allocation_feedback" not in diagnostics["profile_diagnostics"]["optimizer_budget"]
