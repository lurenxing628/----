"""Controlled clock tests run REAL SGS; time control never fabricates a schedule."""
from __future__ import annotations

import pytest

from core.services.scheduler.run.optimizer_graph_ready_budget import GraphReadySearchBudget
from core.services.scheduler.run.optimizer_graph_ready_profiles import graph_ready_v2_profiles
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import EliteRepairLimits
from core.services.scheduler.run.optimizer_graph_ready_stage_scheduler import ROTATION_POLICY
from tests._support.optimizer_graph_ready_benchmark import _schedule_with_scheduler
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case


def _efficiency(result):
    return next(attempt["profile_efficiency"] for attempt in result["attempts"] if "profile_efficiency" in attempt)


def _repaired(kwargs):
    return kwargs["strategy_params"]["graph_ready_profile"]["candidate_origin"] == "graph_ready_v2_repaired"


@pytest.mark.parametrize("cap", [2, 3, 4, 9, 19, 60])
def test_profile_families_interleave_before_cap(cap):
    profiles, truncated, _reason = graph_ready_v2_profiles(max_candidate_profiles=cap, seed=3)
    assert profiles[0].formula_version == "graph_ready_v1"
    assert profiles[1].formula_version.startswith("graph_ready_v2")
    assert len(profiles) == min(cap, 29)
    assert truncated == (cap < 29)
    assert [profile.profile_order for profile in profiles] == list(range(len(profiles)))


@pytest.mark.parametrize("cap", [1, 2, 3, 4, 9, 19, 60])
def test_real_sgs_rotation_never_increases_shared_candidate_cap(cap):
    result = run_production_repair_case(max_candidates=cap, clock=lambda: 0.0)
    efficiency, repair = _efficiency(result), result["repair"]
    # The cap bounds profile and repair decodes; the iterated greedy stage has its own decode cap.
    assert len(result["phase_calls"]) <= cap
    assert efficiency["profile_decodes"] + repair["repair_evaluated_candidates"] == len(result["phase_calls"])
    assert repair["repair_evaluated_candidates"] <= repair["repair_candidate_budget"] <= cap
    assert efficiency["candidate_cap_scope"] == "profiles_and_elite_repair"
    assert result["iterated_greedy"]["decodes"] == len(result["ig_calls"]) <= result["iterated_greedy"]["max_decodes"]
    assert result["state"].evaluated_candidates == len(result["calls"]) + 1
    assert result["best"]["score"] <= result["baseline"]["score"]
    if cap >= 3:
        assert repair["repair_evaluated_candidates"] > 0
        assert efficiency["stage_startup"]["elite_repair"] == {"status": "task_started", "reason": None}


def test_rotation_reaches_available_stages_before_short_real_sgs_deadline():
    now = [0.0]
    starts = []

    def schedule(scheduler, **kwargs):
        starts.append((now[0], _repaired(kwargs)))
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += 0.2
        return result

    result = run_production_repair_case(clock=lambda: now[0], schedule_fn=schedule)
    assert [repair for _time, repair in starts[:2]] == [False, False]
    assert any(repair for _time, repair in starts)
    assert all(start < 1.0 for start, _repair in starts)
    efficiency = _efficiency(result)
    assert efficiency["rotation_policy"] == ROTATION_POLICY
    assert efficiency["rotation_stop_reason"] == "time_budget"
    assert efficiency["profile_decodes"] == efficiency["profile_cost_samples"]
    assert efficiency["mean_profile_cost_ms"] == pytest.approx(200)
    assert all(item["status"] == "task_started" for item in efficiency["stage_startup"].values())
    assert result["repair"]["repair_evaluated_candidates"] >= 1
    assert result["iterated_greedy"]["decodes"] >= 1


def test_profile_construction_crossing_deadline_never_starts_sgs(monkeypatch):
    from core.services.scheduler.run import optimizer_graph_ready_candidates as candidates
    now = [0.0]
    original = candidates.context_for_profile

    def context(**kwargs):
        result = original(**kwargs)
        now[0] = 1.0
        return result

    monkeypatch.setattr(candidates, "context_for_profile", context)
    result = run_production_repair_case(clock=lambda: now[0], iterated_greedy={"enabled": False})
    assert result["calls"] == []
    assert _efficiency(result)["profile_decodes"] == 0
    assert _efficiency(result)["skipped_before_decode"] == 1
    assert result["state"].deadline_reached
    assert result["best"] is result["baseline"]


def test_profile_decode_overrun_finishes_metrics_and_starts_no_second_decode():
    now = [0.0]

    def schedule(scheduler, **kwargs):
        result = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] = 1.5
        return result

    result = run_production_repair_case(clock=lambda: now[0], schedule_fn=schedule, iterated_greedy={"enabled": False})
    assert len(result["calls"]) == 1
    assert _efficiency(result)["profile_decodes"] == 1
    assert result["state"].evaluated_candidates == 2
    assert result["state"].deadline_reached
    assert result["best"]["score"] <= result["baseline"]["score"]
    startup = _efficiency(result)["stage_startup"]
    assert startup["elite_repair"] == {"status": "skipped", "reason": "time_budget"}
    assert startup["iterated_greedy"] == {"status": "skipped", "reason": "disabled"}


def test_candidate_budget_has_no_fixed_time_or_candidate_reservations():
    now = [0.0]
    budget = GraphReadySearchBudget(limits=EliteRepairLimits(max_candidates=4), deadline=1.0, clock=lambda: now[0])
    budget.profile_decodes = 3
    now[0] = 0.8
    assert budget.available()
    assert budget.remaining_candidates() == 1
    off = GraphReadySearchBudget(limits=EliteRepairLimits(enabled=False), deadline=1.0, clock=lambda: 0.0)
    assert off.available() and off.remaining_candidates() == 60
    assert off.summary()["candidate_cap_scope"] == "profiles_and_elite_repair"


def test_disabled_repair_still_prunes_profiles_without_reporting_fake_evaluations():
    result = run_production_repair_case(enabled=False, clock=lambda: 0.0)
    report = _efficiency(result)
    assert report["considered_profiles"] == 29
    assert report["predecode_pruned_profiles"] > 0
    assert report["profile_decodes"] == len(result["calls"]) < 29
    assert report["profile_decodes"] + report["predecode_pruned_profiles"] == 29
    assert result["repair"]["repair_status"] == "not_run"
    assert result["repair"]["repair_evaluated_candidates"] == 0


@pytest.mark.parametrize("cap", [1, 3, 9, 19, 60])
def test_profile_diagnostics_count_conservation_and_shared_paths(cap):
    result = run_production_repair_case(max_candidates=cap, clock=lambda: 0.0)
    report = _efficiency(result)
    assert report == result["state"].candidate_profile["graph_ready_optimization"]["profile_efficiency"]
    assert report["configured_profiles"] == report["considered_profiles"] + report["unvisited_profiles"]
    assert report["considered_profiles"] == sum(report[key] for key in (
        "profile_decodes", "predecode_pruned_profiles", "construction_rejected_profiles", "skipped_before_decode"))


def test_construction_validation_is_not_counted_as_a_decode(monkeypatch):
    from core.infrastructure.errors import ValidationError
    from core.services.scheduler.run import optimizer_graph_ready_candidates as candidates
    original = candidates.context_for_profile

    def context(**kwargs):
        if kwargs["profile"].slug == "balanced":
            raise ValidationError("controlled construction failure", field="graph_ready_context")
        return original(**kwargs)

    monkeypatch.setattr(candidates, "context_for_profile", context)
    result = run_production_repair_case(enabled=False, clock=lambda: 0.0, strict_mode=False)
    report = _efficiency(result)
    assert report["construction_rejected_profiles"] == 1
    assert report["profile_decodes"] == len(result["calls"])
    assert report["considered_profiles"] == report["profile_decodes"] + report["predecode_pruned_profiles"] + 1


@pytest.mark.parametrize("decode_seconds", [0.0, 0.001])
def test_real_same_output_baseline_cannot_become_a_fake_strict_improvement(decode_seconds):
    now = [0.0]

    def schedule(scheduler, **kwargs):
        candidate = _schedule_with_scheduler(scheduler, **kwargs)
        now[0] += decode_seconds
        return candidate

    result = run_production_repair_case(clock=lambda: now[0], schedule_fn=schedule)
    summary = result["state"].finalize(runtime_ms=0, attempts=result["attempts"], improvement_trace=result["trace"])
    assert result["best"]["summary"].failed_ops == 0
    assert result["best"]["score"] <= result["baseline"]["score"]
    assert all(event["acceptance_name"] == "improve_only" and event["accepted"] for event in result["state"].acceptance_events)
    assert summary["improved"] == (result["best"]["score"] < result["baseline"]["score"])
    strict_events = [event for event in result["state"].acceptance_events if event["acceptance_reason"] == "score_improved"]
    assert sum(_efficiency(result)["stage_strict_improvements"].values()) == len(strict_events)
    if decode_seconds == 0:
        assert set(_efficiency(result)["stage_recent_improvements_per_second"].values()) == {0.0}


def test_strict_and_nonstrict_decode_failures_count_started_sgs_only():
    from core.infrastructure.errors import ValidationError

    def schedule(scheduler, **kwargs):
        raise ValidationError("controlled decode failure", field="schedule")

    result = run_production_repair_case(clock=lambda: 0.0, schedule_fn=schedule, strict_mode=False)
    assert _efficiency(result)["profile_decodes"] == len(result["phase_calls"]) == 29
    # The iterated greedy stage stops once the decoder rejects its decisions (the parent's own order first).
    assert result["iterated_greedy"]["stop_reason"] in {"parent_order_rejected", "decoder_rejections", "search_space_exhausted"}
    assert _efficiency(result)["predecode_pruned_profiles"] == 0
    assert result["best"] is result["baseline"]
    with pytest.raises(ValidationError, match="controlled decode failure"):
        run_production_repair_case(clock=lambda: 0.0, schedule_fn=schedule, strict_mode=True)


def test_profile_cost_remains_measured_without_reserving_a_time_slice():
    now = [0.0]
    budget = GraphReadySearchBudget(limits=EliteRepairLimits(), deadline=1.0, clock=lambda: now[0])
    budget.profile_decodes = 2
    budget.record_profile_cost(0.08)
    budget.record_profile_cost(0.12)
    now[0] = 0.95
    assert budget.available()
    report = budget.summary()
    assert report["stop_reason"] is None
    assert report["mean_profile_cost_ms"] == pytest.approx(100)
    assert budget.deadline == 1.0 and budget.max_candidates == 60
    now[0] = 1.0
    assert not budget.available() and budget.stop_reason == "time_budget"


def test_shared_cap_remains_hard_and_does_not_convert_local_repair_time_to_a_reservation():
    now = [0.0]
    limits = EliteRepairLimits(max_candidates=9, max_neighbors_per_elite=1, time_budget_ms=5)
    budget = GraphReadySearchBudget(limits=limits, deadline=1.0, clock=lambda: now[0])
    budget.profile_decodes = 2
    budget.record_profile_cost(0.1)
    now[0] = 0.7
    assert budget.available()
    assert budget.summary()["mean_profile_cost_ms"] == pytest.approx(100)
    budget.profile_decodes = 9
    assert not budget.available()
    assert budget.stop_reason == "candidate_budget"


def test_enabled_and_disabled_repair_share_the_same_outer_time_contract():
    now = [0.0]
    limits = EliteRepairLimits()
    budget = GraphReadySearchBudget(limits=limits, deadline=1.0, clock=lambda: now[0])
    budget.record_profile_cost(0.2)
    now[0] = 0.7
    assert budget.available()
    off = GraphReadySearchBudget(limits=EliteRepairLimits(enabled=False), deadline=1.0, clock=lambda: now[0])
    off.record_profile_cost(0.2)
    assert off.available()
    now[0] = 1.0
    assert not budget.available() and not off.available()
    assert budget.stop_reason == off.stop_reason == "time_budget"


@pytest.mark.parametrize("duration", [-1.0, float("inf"), float("nan"), True])
def test_profile_cost_rejects_invalid_elapsed_time(duration):
    budget = GraphReadySearchBudget(limits=EliteRepairLimits(), deadline=1.0, clock=lambda: 0.0)
    with pytest.raises(ValueError, match="finite and nonnegative"):
        budget.record_profile_cost(duration)


def test_zero_clock_samples_do_not_invent_profile_cost():
    budget = GraphReadySearchBudget(limits=EliteRepairLimits(), deadline=1.0, clock=lambda: 0.0)
    budget.record_profile_cost(0.0)
    assert budget.available()
    assert budget.summary()["profile_cost_samples"] == 0
    assert budget.summary()["mean_profile_cost_ms"] is None
