"""Deadline guards keep configuration failures and forbid late SGS starts."""
from __future__ import annotations

from types import SimpleNamespace
from typing import cast

import pytest

from core.infrastructure.errors import ValidationError
from core.services.scheduler.run import optimizer_graph_ready_profile_selection as selection
from core.services.scheduler.run import optimizer_graph_ready_repair as repair
from core.services.scheduler.run import optimizer_graph_ready_repair_decisions as decisions
from core.services.scheduler.run.optimizer_graph_ready_repair_contract import EliteRepairLimits, new_repair_report
from tests._support.optimizer_graph_ready_repair_benchmark import run_production_repair_case


def test_exhausted_deadline_skips_v2_feature_construction(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("exhausted search must not construct v2 capacity metrics")

    monkeypatch.setattr(selection, "enrich_graph_ready_v2_metrics", forbidden)
    result = run_production_repair_case(time_budget_seconds=0, clock=lambda: 0.0, keep_report=False)
    assert result["calls"] == []
    assert result["best"] == result["baseline"]


@pytest.mark.parametrize("strict_mode", [False, True])
def test_exhausted_deadline_does_not_hide_invalid_repair_configuration(strict_mode):
    with pytest.raises(ValidationError) as exc:
        run_production_repair_case(time_budget_seconds=0, clock=lambda: 0.0,
                                   limits={"max_rounds": 0}, strict_mode=strict_mode)
    assert exc.value.field == "graph_ready_elite_repair"


def test_deadline_is_rechecked_after_operation_resource_decision_construction(monkeypatch):
    now = [0.0]
    apply = decisions.apply_repair_decision

    def construct(*args, **kwargs):
        value = apply(*args, **kwargs)
        now[0] += 0.006
        return value

    monkeypatch.setattr(decisions, "apply_repair_decision", construct)
    result = run_production_repair_case(limits={"time_budget_ms": 5}, clock=lambda: now[0])
    report = result["repair"]
    pruning = report["repair_pruning_report"]
    assert report["repair_evaluated_candidates"] == 0
    assert report["repair_stop_reason"] == "time_budget"
    assert report["repair_status"] == "skipped_by_budget"
    assert pruning["pruned_by_rule"]["budget_before_decode"] == 1
    assert pruning["generated_candidates"] == pruning["evaluated_candidates"] + pruning["pruned_candidates"]
    assert not any(call["strategy_params"]["graph_ready_profile"]["candidate_origin"] == "graph_ready_v2_repaired"
                   for call in result["calls"])


@pytest.mark.parametrize("boundary", ["candidate_budget", "time_budget", "next_round_construction"])
def test_terminal_budget_counts_unvisited_deferred_elites_once(monkeypatch, boundary):
    limits = EliteRepairLimits(top_k=2, max_neighbors_per_elite=1, max_rounds=3)
    report = new_repair_report(limits, objective_name="min_overdue")
    report["repair_candidate_budget"] = 1 if boundary == "candidate_budget" else 10
    pruning = report["repair_pruning_report"]
    pruning["candidate_space_total"] = 8
    elites = [{"neighborhood": SimpleNamespace(candidate_count=size)} for size in (3, 5)]
    pool = cast(repair.EliteRepairPool, SimpleNamespace(limits=limits, report=report, elites=elites))
    improved = {"score": (0, 1)}
    visited = []
    after_improvement_reads = []

    def clock():
        if visited:
            after_improvement_reads.append(None)
            if boundary == "time_budget" or (boundary == "next_round_construction" and len(after_improvement_reads) >= 2):
                return 1.0
        return 0.0

    def bounded_improving_elite(_pool, **kwargs):
        # Isolate the post-decode boundary; exercise the real decode-budget guard.
        kwargs["before_decode"]()
        visited.append(kwargs["elite"])
        kwargs["elite"]["decision_offset"] = 1
        pruning["generated_candidates"] += 1
        pruning["skipped_by_budget"] += kwargs["elite"]["neighborhood"].candidate_count - 1
        kwargs["improved_elites"].append({"candidate": improved, "profile": None})
        return improved

    monkeypatch.setattr(repair, "_repair_one_elite", bounded_improving_elite)
    best = repair._repair_elites(
        pool, best=None, evaluate=lambda **_kwargs: {}, repair_deadline=1.0, clock=clock, t_begin=0.0,
        attempts=[], improvement_trace=[], report_state=None, strict_mode=True,
    )
    assert best is improved and visited == [elites[0]]
    assert report["repair_stop_reason"] == ("candidate_budget" if boundary == "candidate_budget" else "time_budget")
    assert report["repair_deferred_by_improvement"] == 7
    assert pruning["evaluated_candidates"] == pruning["generated_candidates"] == 1
    assert pruning["skipped_by_budget"] == 7
    assert pruning["candidate_space_total"] == pruning["generated_candidates"] + pruning["skipped_by_budget"]


@pytest.mark.parametrize("boundary", ["continue", "candidate_budget", "time_budget", "max_rounds"])
@pytest.mark.parametrize("tail_size", [2, 3])
def test_pending_tail_survives_a_quiet_full_active_round(monkeypatch, boundary, tail_size):
    limits = EliteRepairLimits(top_k=1, max_neighbors_per_elite=1,
                               max_rounds=2 if boundary == "max_rounds" else tail_size + 1)
    report = new_repair_report(limits, objective_name="min_overdue")
    report["repair_candidate_budget"] = 2 if boundary == "candidate_budget" else 60
    pruning = report["repair_pruning_report"]
    pruning["candidate_space_total"] = tail_size
    elite = {"label": "original", "decision_offset": 0, "neighborhood": SimpleNamespace(candidate_count=tail_size)}
    visited = []

    def make_elite(candidate, profile):
        assert candidate["score"] == (0, 5)
        return {"label": "improved", "decision_offset": 0, "neighborhood": SimpleNamespace(candidate_count=1)}

    pool = cast(repair.EliteRepairPool, SimpleNamespace(limits=limits, report=report, elites=[elite], make_elite=make_elite))

    def visit(_pool, **kwargs):
        current = kwargs["elite"]
        offset = current["decision_offset"]
        assert kwargs["elite_index"] == 0, "pending tails cannot exceed the active top-k limit"
        kwargs["before_decode"]()
        visited.append((current["label"], offset))
        current["decision_offset"] += 1
        pruning["generated_candidates"] += 1
        pruning["skipped_by_budget"] += current["neighborhood"].candidate_count - current["decision_offset"]
        score = 6
        if current["label"] == "original":
            score = 5 if offset == 0 else (1 if offset == tail_size - 1 else 6)
        candidate = {"score": (0, score)}
        if candidate["score"] < kwargs["best"]["score"]:
            kwargs["improved_elites"].append({"candidate": candidate, "profile": None})
            return candidate
        return kwargs["best"]

    def clock():
        return 1.0 if boundary == "time_budget" and len(visited) >= 2 else 0.0

    monkeypatch.setattr(repair, "_repair_one_elite", visit)
    best = repair._repair_elites(
        pool, best={"score": (0, 10)}, evaluate=lambda **_kwargs: {}, repair_deadline=1.0,
        clock=clock, t_begin=0.0, attempts=[], improvement_trace=[], report_state=None, strict_mode=True,
    )
    expected = [("original", 0), ("improved", 0)]
    if boundary == "continue":
        expected.extend(("original", offset) for offset in range(1, tail_size))
    assert visited == expected
    assert best is not None
    assert best["score"] == (0, 1 if boundary == "continue" else 5)
    assert report["repair_stop_reason"] == ("max_rounds" if boundary == "continue" else boundary)
    assert report["repair_round_improvements"][:2] == [1, 0]
    assert pruning["candidate_space_total"] == tail_size + 1
    assert pruning["generated_candidates"] == pruning["evaluated_candidates"] == len(visited)
    assert pruning["skipped_by_budget"] == tail_size + 1 - len(visited)
