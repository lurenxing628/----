"""Freeze the actual candidate decision and its permanent-reference evidence."""

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.services.scheduler.run.schedule_candidate_health import CandidateHealth, evaluate_candidate_health
from core.services.scheduler.run.schedule_candidate_plan import CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import CandidateSelectionResult, select_candidate_plan
from data.repositories.workbench_run_result_repo import _selection_references


def _candidate(key, *, sequence, overdue=2, weighted=10.0, tardiness=10.0, health_state="same"):
    metrics = ScheduleMetrics(
        overdue_count=overdue,
        total_tardiness_hours=tardiness,
        weighted_tardiness_hours=weighted,
        makespan_hours=20.0,
        changeover_count=1,
    )
    health = CandidateHealth(
        state=health_state,
        score=2 if health_state == "better" else 0,
        reason_code="critical_chain_" + health_state,
        critical_chain_finish_hours_delta=-1.0,
        critical_chain_wait_hours_delta=-1.0,
        top_impact_ops_avg_start_hours_delta=None,
        critical_chain_slack_hours_delta=None,
        critical_chain_node_count=2,
        top_impact_op_count=0,
    )
    return CandidatePlan(
        sequence=sequence,
        candidate_key=key,
        kind="baseline" if key == "baseline" else "critical_chain",
        label=key,
        status="completed",
        score=(0.0,) + objective_score("min_overdue", metrics),
        graph_critical_weight=0 if key == "baseline" else 500,
        graph_impact_weight=0 if key == "baseline" else 10,
        graph_downstream_weight=0 if key == "baseline" else 1,
        metrics=metrics,
        health=health,
        objective="min_overdue",
        objective_name="min_overdue",
    )


def _evidence(selection):
    evidence = selection.decision_evidence
    assert evidence["version"] == "candidate-selection-evidence-v1"
    assert evidence["state"] == "complete"
    return evidence


def test_complete_score_and_baseline_sequence_ties_record_the_actual_decision():
    baseline = _candidate("baseline", sequence=0, weighted=11.0)
    graph = _candidate("graph-first", sequence=1)
    skipped = replace(_candidate("skipped", sequence=2, overdue=0), status="skipped", score=None)
    selection = select_candidate_plan([skipped, graph, baseline], policy="score_only")
    assert selection.selected_candidate_key == graph.candidate_key
    saved = _selection_references(selection, [
        {"key": candidate.candidate_key, "candidate_ref": "ref-" + candidate.candidate_key,
         "artifact": {"objective_name": candidate.objective_name, "score": list(candidate.score or [])}}
        for candidate in (baseline, graph, skipped)
    ])
    assert saved["selection_policy"] == "score_only"
    assert saved["overdue_tolerance_count"] is None and saved["tardiness_tolerance_ratio"] is None
    tie = _evidence(selection)["tiebreak"]
    assert tie["rule"] == "full_score_baseline_sequence_v1"
    assert set(tie["primary_tied_candidate_keys"]) == {baseline.candidate_key, graph.candidate_key}
    assert tie["full_score_tied_candidate_keys"] == [graph.candidate_key]
    assert tie["runner_up_candidate_key"] == baseline.candidate_key
    assert tie["decisive_step"] == "secondary_score"
    assert tie["decisive_score_index"] == 2
    assert _evidence(selection)["balanced_checks"]["reason_code"] == "score_only"

    baseline_tied = _candidate("baseline", sequence=0)
    selection = select_candidate_plan([graph, baseline_tied], policy="score_only")
    assert selection.selected_candidate_key == "baseline"
    tie = _evidence(selection)["tiebreak"]
    assert set(tie["full_score_tied_candidate_keys"]) == {"baseline", graph.candidate_key}
    assert tie["decisive_step"] == "baseline_preference"
    assert tie["decisive_score_index"] is None

    later = _candidate("graph-later", sequence=3)
    selection = select_candidate_plan([later, graph], policy="score_only")
    assert selection.selected_candidate_key == graph.candidate_key
    tie = _evidence(selection)["tiebreak"]
    assert tie["runner_up_candidate_key"] == later.candidate_key
    assert tie["decisive_step"] == "candidate_sequence"
    assert tie["decisive_score_index"] is None


def test_balanced_records_four_checks_and_min_overdue_primary_blocks_plus_one():
    baseline = _candidate("baseline", sequence=0)
    graph = _candidate("graph-first", sequence=1, weighted=11.0, tardiness=10.75, health_state="better")
    selection = select_candidate_plan([baseline, graph], graph_overdue_tolerance_count=1,
                                      graph_tardiness_tolerance_ratio=0.10)
    assert selection.selected_candidate_key == graph.candidate_key
    assert selection.raw_score_best_key == baseline.candidate_key
    evidence = _evidence(selection)
    checks = evidence["balanced_checks"]
    assert checks["eligible"] is True and checks["checked"] is True
    assert checks["accepted"] is True and checks["override_applied"] is True
    assert checks["candidate_key"] == graph.candidate_key
    assert checks["reference_candidate_key"] == baseline.candidate_key
    assert checks["health_reference_candidate_key"] == baseline.candidate_key
    assert checks["health_state"] == "better"
    values = {item["key"]: item for item in checks["checks"]}
    assert list(values) == ["failed_ops", "objective_primary_score", "overdue_count", "total_tardiness_hours"]
    assert all(item["passed"] for item in values.values())
    assert values["failed_ops"]["limit"] == 0.0
    assert values["failed_ops"]["tolerance"] is None
    assert values["objective_primary_score"]["candidate_value"] == 2.0
    assert values["objective_primary_score"]["limit"] == 2.0
    assert values["objective_primary_score"]["tolerance"] is None
    assert values["overdue_count"]["limit"] == 3.0
    assert values["overdue_count"]["tolerance"] == 1
    assert values["total_tardiness_hours"]["candidate_value"] == 10.75
    assert values["total_tardiness_hours"]["reference_value"] == 10.0
    assert values["total_tardiness_hours"]["limit"] == pytest.approx(11.0)
    assert values["total_tardiness_hours"]["tolerance"] == 0.10
    assert evidence["selected"]["total_tardiness_hours"] == 10.75
    assert evidence["anchors"]["raw_score_best"]["total_tardiness_hours"] == 10.0

    graph_plus_one = _candidate("graph-first", sequence=1, overdue=3, weighted=11.0,
                                tardiness=10.75, health_state="better")
    rejected = select_candidate_plan([baseline, graph_plus_one], graph_overdue_tolerance_count=1,
                                    graph_tardiness_tolerance_ratio=0.10)
    assert rejected.selected_candidate_key == baseline.candidate_key
    checks = _evidence(rejected)["balanced_checks"]
    assert checks["eligible"] is True and checks["checked"] is True
    assert checks["accepted"] is False and checks["override_applied"] is False
    values = {item["key"]: item for item in checks["checks"]}
    assert values["objective_primary_score"]["candidate_value"] == 3.0
    assert values["objective_primary_score"]["reference_value"] == 2.0
    assert values["objective_primary_score"]["passed"] is False
    assert values["overdue_count"]["passed"] is True
    assert values["total_tardiness_hours"]["passed"] is True


def test_balanced_selected_raw_has_zero_difference_and_no_override():
    baseline = _candidate("baseline", sequence=0, overdue=3, weighted=15.0, tardiness=15.0)
    graph = _candidate("graph-first", sequence=1, health_state="better")
    selection = select_candidate_plan([baseline, graph])
    assert selection.selected_candidate_key == selection.raw_score_best_key == graph.candidate_key
    evidence = _evidence(selection)
    checks = evidence["balanced_checks"]
    assert checks["accepted"] is True
    assert checks["override_applied"] is False
    assert checks["reference_candidate_key"] == graph.candidate_key
    assert checks["health_reference_candidate_key"] == baseline.candidate_key
    assert all(item["candidate_value"] - item["reference_value"] == 0.0 for item in checks["checks"])
    assert evidence["selected"] == evidence["anchors"]["raw_score_best"]
    assert evidence["anchors"]["health_reference"]["candidate_key"] == baseline.candidate_key


def test_health_evidence_preserves_unrounded_deltas_and_actual_tolerance_contributions():
    origin = datetime(2026, 10, 1, 8)

    def result(op_id, start, end):
        return SimpleNamespace(op_id=op_id, start_time=origin + timedelta(hours=start),
                               end_time=origin + timedelta(hours=end))

    health = evaluate_candidate_health(
        baseline_results=[result(1, 0.0, 1.0), result(2, 3.0, 4.0)],
        candidate_results=[result(1, -0.01004, 0.98996), result(2, 2.88992, 3.78992)],
        graph_metrics={"critical_path_op_ids": [1, 2], "top_impact_op_ids": [1, 2],
                       "critical_chain_slack_hours_delta": 0.01004},
    )
    assert health.state == "better" and health.score == 4
    assert health.critical_chain_finish_hours_delta == -0.2
    assert health.critical_chain_wait_hours_delta == -0.1
    assert health.critical_chain_slack_hours_delta == 0.01
    evidence = health.decision_evidence
    assert evidence["version"] == "candidate-health-evidence-v1"
    assert evidence["state"] == "complete"
    assert evidence["relative_tolerance_ratio"] == 0.05
    assert evidence["neutral_tolerance_hours"] == 0.01
    assert evidence["score_thresholds"] == {"better_min": 2, "worse_max": -2}
    components = {item["key"]: item for item in evidence["components"]}
    finish = components["critical_chain_finish_hours_delta"]
    assert finish["basis"] == "critical_path_span"
    assert finish["reference_value"] == 4.0
    assert finish["candidate_value"] == pytest.approx(3.79996)
    assert finish["delta_hours"] == pytest.approx(-0.20004)
    assert finish["tolerance_hours"] == pytest.approx(0.2)
    wait = components["critical_chain_wait_hours_delta"]
    assert wait["basis"] == "critical_path_wait"
    assert wait["reference_value"] == 2.0
    assert wait["candidate_value"] == pytest.approx(1.89996)
    assert wait["delta_hours"] == pytest.approx(-0.10004)
    assert wait["tolerance_hours"] == pytest.approx(0.1)
    start = components["top_impact_ops_avg_start_hours_delta"]
    assert start["basis"] == "common_origin_mean_start"
    assert start["reference_value"] == pytest.approx(1.5)
    assert start["candidate_value"] == pytest.approx(1.43994)
    assert start["delta_hours"] == pytest.approx(-0.06006)
    assert start["origin"] == origin.isoformat()
    slack = components["critical_chain_slack_hours_delta"]
    assert slack["basis"] == "saved_slack_delta"
    assert slack["reference_value"] is None and slack["candidate_value"] is None
    assert slack["delta_hours"] == pytest.approx(0.01004)
    assert slack["tolerance_hours"] == 0.01
    assert slack["improvement"] == "higher"
    assert all(components[key]["improvement"] == "lower" for key in components if key != slack["key"])
    assert all(item["state"] == "complete" and item["contribution"] == 1 for item in components.values())
    assert sum(item["contribution"] for item in components.values()) == health.score


def test_nested_evidence_maps_permanent_references_and_keeps_fixed_anchors_and_legacy_default():
    baseline = _candidate("baseline", sequence=0)
    graph = _candidate("graph-first", sequence=1, weighted=11.0, tardiness=10.75, health_state="better")
    third = _candidate("graph-third", sequence=2, overdue=4, weighted=30.0, tardiness=30.0)
    selection = select_candidate_plan([baseline, graph, third])
    original_evidence = deepcopy(_evidence(selection))
    refs = {baseline.candidate_key: "ref-baseline", graph.candidate_key: "ref-graph", third.candidate_key: "ref-third"}
    rows = [{"key": candidate.candidate_key, "candidate_ref": refs[candidate.candidate_key],
             "artifact": {"objective_name": candidate.objective_name, "score": list(candidate.score)}}
            for candidate in (baseline, graph, third)]
    baseline.metrics.overdue_count = 99
    saved = _selection_references(selection, rows)
    evidence = saved["decision_evidence"]
    assert saved["selected_candidate_ref"] == refs[graph.candidate_key]
    assert saved["raw_score_best_candidate_ref"] == saved["health_reference_candidate_ref"] == refs[baseline.candidate_key]
    assert evidence["selected"]["candidate_ref"] == refs[graph.candidate_key]
    assert evidence["anchors"]["raw_score_best"]["candidate_ref"] == refs[baseline.candidate_key]
    assert evidence["anchors"]["health_reference"]["candidate_ref"] == refs[baseline.candidate_key]
    assert evidence["anchors"]["raw_score_best"]["overdue_count"] == 2.0
    assert evidence["anchors"]["health_reference"]["overdue_count"] == 2.0
    tie = evidence["tiebreak"]
    assert set(tie["primary_tied_candidate_refs"]) == {refs[baseline.candidate_key], refs[graph.candidate_key]}
    assert tie["full_score_tied_candidate_refs"] == [refs[baseline.candidate_key]]
    assert tie["raw_score_best_candidate_ref"] == refs[baseline.candidate_key]
    assert tie["runner_up_candidate_ref"] == refs[graph.candidate_key]
    checks = evidence["balanced_checks"]
    assert checks["candidate_ref"] == refs[graph.candidate_key]
    assert checks["reference_candidate_ref"] == checks["health_reference_candidate_ref"] == refs[baseline.candidate_key]
    assert selection.decision_evidence == original_evidence

    def fields(value):
        if isinstance(value, dict):
            for key, item in value.items():
                yield key
                yield from fields(item)
        elif isinstance(value, list):
            for item in value:
                yield from fields(item)

    assert not any(key.endswith(("candidate_key", "candidate_keys")) for key in fields(evidence))
    legacy = CandidateSelectionResult(
        selected_candidate_key=graph.candidate_key, selected_kind=graph.kind, selection_policy="balanced",
        reason_code="balanced_critical_health_better", raw_score_best_key=baseline.candidate_key,
        baseline_best_key=baseline.candidate_key, critical_best_key=graph.candidate_key,
        critical_health_best_key=graph.candidate_key, selected_score=graph.score, selected_plan=graph,
    )
    assert legacy.decision_evidence is None
    legacy_saved = _selection_references(legacy, rows)
    assert legacy_saved["selected_candidate_ref"] == refs[graph.candidate_key]
    assert legacy_saved.get("decision_evidence") is None
