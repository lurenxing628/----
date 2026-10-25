"""Freeze the actual candidate decision and its permanent-reference evidence."""

from copy import deepcopy
from dataclasses import replace

import pytest

from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.models.objective import objective_metric_keys, target_objectives_for
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_candidate_plan import CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import (
    BusinessObjectiveSelectionResult,
)
from core.services.workbench.facts.decision_selection import selection_basis, selection_roles
from core.services.workbench.run.result_preparation import _selection_references
from tests.workbench.legacy_run_archive_support import stored_legacy_selection


def _candidate(key, *, sequence, overdue=2, weighted=10.0, tardiness=10.0, health_state="same"):
    metrics = ScheduleMetrics(
        overdue_count=overdue,
        total_tardiness_hours=tardiness,
        weighted_tardiness_hours=weighted,
        makespan_hours=20.0,
        changeover_count=1,
    )
    health = {"state": health_state, "score": 2 if health_state == "better" else 0,
        "reason_code": "critical_chain_" + health_state,
        "critical_chain_finish_hours_delta": -1.0, "critical_chain_wait_hours_delta": -1.0,
        "top_impact_ops_avg_start_hours_delta": None, "critical_chain_slack_hours_delta": None,
        "critical_chain_node_count": 2, "top_impact_op_count": 0}
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


def test_nested_evidence_maps_permanent_references_and_keeps_fixed_anchors_and_legacy_default():
    baseline = _candidate("baseline", sequence=0)
    graph = _candidate("graph-first", sequence=1, weighted=11.0, tardiness=10.75, health_state="better")
    third = _candidate("graph-third", sequence=2, overdue=4, weighted=30.0, tardiness=30.0)
    # Explicit historical storage material; the retired selector is not executed.
    baseline_snapshot = {"candidate_key": "baseline", "score": list(baseline.score),
        "failed_ops": 0.0, "primary_score": 2.0, "overdue_count": 2.0, "total_tardiness_hours": 10.0}
    selection = stored_legacy_selection({
        "selected_candidate_key": "graph-first", "selected_kind": "critical_chain", "selection_policy": "balanced",
        "reason_code": "balanced_critical_health_better", "raw_score_best_key": "baseline",
        "baseline_best_key": "baseline", "critical_best_key": "graph-first", "critical_health_best_key": "graph-first",
        "selected_score": list(graph.score), "selection_policy_version": "candidate-selection-v1",
        "overdue_tolerance_count": 1, "tardiness_tolerance_ratio": 0.10,
        "decision_evidence": {"version": "candidate-selection-evidence-v1", "state": "complete",
            "anchors": {"raw_score_best": deepcopy(baseline_snapshot), "health_reference": deepcopy(baseline_snapshot)},
            "selected": {"candidate_key": "graph-first", "score": list(graph.score),
                "failed_ops": 0.0, "primary_score": 2.0, "overdue_count": 2.0, "total_tardiness_hours": 10.75},
            "tiebreak": {"rule": "full_score_baseline_sequence_v1", "raw_score_best_candidate_key": "baseline",
                "runner_up_candidate_key": "graph-first", "decisive_step": "secondary_score", "decisive_score_index": 2,
                "primary_tied_candidate_keys": ["baseline", "graph-first"], "full_score_tied_candidate_keys": ["baseline"]},
            "balanced_checks": {"eligible": True, "checked": True, "reason_code": None,
                "candidate_key": "graph-first", "reference_candidate_key": "baseline", "health_reference_candidate_key": "baseline",
                "health_state": "better", "checks": [
                    {"key": "failed_ops", "candidate_value": 0.0, "reference_value": 0.0, "limit": 0.0, "passed": True, "tolerance": None},
                    {"key": "objective_primary_score", "candidate_value": 2.0, "reference_value": 2.0, "limit": 2.0, "passed": True, "tolerance": None},
                    {"key": "overdue_count", "candidate_value": 2.0, "reference_value": 2.0, "limit": 3.0, "passed": True, "tolerance": 1},
                    {"key": "total_tardiness_hours", "candidate_value": 10.75, "reference_value": 10.0, "limit": 11.0, "passed": True, "tolerance": 0.10}],
                "accepted": True, "override_applied": True}},
    }, graph)
    original_evidence = deepcopy(_evidence(selection))
    refs = {baseline.candidate_key: "ref-baseline", graph.candidate_key: "ref-graph", third.candidate_key: "ref-third"}
    rows = [{"key": candidate.candidate_key, "candidate_ref": refs[candidate.candidate_key],
             "artifact": {"objective_name": candidate.objective_name, "score": list(candidate.score)}}
            for candidate in (baseline, graph, third)]
    baseline.metrics.overdue_count = 99
    saved = _selection_references(selection, rows, identities={}, batch_refs={})
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
    legacy = stored_legacy_selection({**selection.to_dict(), "decision_evidence": None}, graph)
    assert legacy.decision_evidence is None
    legacy_saved = _selection_references(legacy, rows, identities={}, batch_refs={})
    assert legacy_saved["selected_candidate_ref"] == refs[graph.candidate_key]
    assert legacy_saved.get("decision_evidence") is None


    # The new persisted selector retains unknown positions and maps winners and scope by value.
    targets = target_objectives_for("min_overdue")
    order = {target: ["failed_ops"] + list(objective_metric_keys(target)) for target in targets}
    scope = {"scheduled_operation_ids": [1, 2], "complete_batch_ids": ["B1"],
             "objective_scope": "unknown", "components_known": False, "is_complete": False}
    new_selection = BusinessObjectiveSelectionResult(
        selected_candidate_key=graph.candidate_key, selected_plan=graph, primary_objective=targets[0],
        target_objectives=targets, objective_winners=dict.fromkeys(targets),
        objective_winner_reasons=dict.fromkeys(targets, "score_components_unavailable"),
        objective_field_order=order, selected_score=(2.0,) + (float("inf"),) * (len(order[targets[0]]) - 1),
        scoring_scope=scope, reason_code="partial_scope_score_unavailable", evidence_state="partial")
    unknown = _selection_references(new_selection, rows, identities={1: "1" * 48, 2: "2" * 48}, batch_refs={"B1": "3" * 48})
    assert unknown["selected_candidate_ref"] == refs[graph.candidate_key]
    assert unknown["objective_winners"] == dict.fromkeys(targets)
    assert unknown["objective_winner_reasons"] == dict.fromkeys(targets, "score_components_unavailable")
    assert unknown["selected_score"] == [2.0] + [None] * (len(order[targets[0]]) - 1)
    assert unknown["objective_field_order"] == order
    assert unknown["scoring_scope"] == {"scheduled_operation_refs": ["1" * 48, "2" * 48], "complete_batch_refs": ["3" * 48],
        "objective_scope": "unknown", "components_known": False, "is_complete": False}
    basis = selection_basis({"selection": unknown}, rows)
    assert basis["raw_score_best_candidate_ref"] == basis["selected_candidate_ref"] == refs[graph.candidate_key]
    assert basis["health_reference_candidate_ref"] is basis["health_comparison"] is None
    assert basis["evidence_state"] == "partial" and basis["scoring_scope"] == unknown["scoring_scope"]
    assert selection_roles(rows[1], basis) == ["recommended"]
    assert all("algorithm_baseline" not in selection_roles(row, basis) for row in rows)
    assert basis["explanation"]["issues"][0]["code"] == "score_components_unavailable"
    with pytest.raises(ValueError):
        durable_value({"unrelated_product_value": float("inf")})

    known = replace(new_selection, objective_winners={target: rows[index]["key"]
                    for index, target in enumerate(targets)}, objective_winner_reasons=dict.fromkeys(targets),
                    selected_score=graph.score, scoring_scope={**scope, "components_known": True},
                    reason_code="primary_objective_best_in_completed_scope")
    mapped = _selection_references(known, rows, identities={1: "1" * 48, 2: "2" * 48}, batch_refs={"B1": "3" * 48})
    assert mapped["objective_winners"] == {target: rows[index]["candidate_ref"] for index, target in enumerate(targets)}
    assert mapped["selected_score"] == list(graph.score) and mapped["objective_field_order"] == order
