"""Freeze the actual candidate decision and its permanent-reference evidence."""

from dataclasses import replace

import pytest

from core.algorithm_contracts.types import ScheduleSummary
from core.algorithms.evaluation import ScheduleMetrics, objective_score
from core.algorithms.evaluation_completion import BatchCompletion
from core.models.objective import objective_metric_keys, target_objectives_for
from core.models.workbench_run_job import durable_value
from core.services.scheduler.run.schedule_candidate_plan import CandidatePlan
from core.services.scheduler.run.schedule_candidate_selection import (
    BusinessObjectiveSelectionResult,
)
from core.services.workbench.facts.decision_selection import selection_basis, selection_roles
from core.services.workbench.run.result_preparation import _selection_references

COMPLETE = BatchCompletion(expected_operation_count=2, missing_operation_count=0, unexpected_result_count=0,
                           complete_batch_count=2, incomplete_batch_ids=(), partial_batch_ids=(),
                           failure_detail_count=0, failure_batch_ids=())


def _candidate(key, *, sequence, overdue=2, weighted=10.0, tardiness=10.0):
    metrics = ScheduleMetrics(
        overdue_count=overdue,
        total_tardiness_hours=tardiness,
        weighted_tardiness_hours=weighted,
        makespan_hours=20.0,
        changeover_count=1,
        completion=COMPLETE,
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
        summary=ScheduleSummary(
            success=True,
            total_ops=2,
            scheduled_ops=2,
            failed_ops=0,
            warnings=[],
            errors=[],
            duration_seconds=0.0,
        ),
        metrics=metrics,
        generation_policy_version="unified_search_v1",
        origin={"origin": key},
        first_found_elapsed_ms=0,
        search_evidence_ref={"source_event_id": None},
        objective_name="min_overdue",
    )


def test_business_selection_maps_winners_and_scope_to_permanent_references():
    baseline = _candidate("baseline", sequence=0)
    graph = _candidate("graph-first", sequence=1, weighted=11.0, tardiness=10.75)
    third = _candidate("graph-third", sequence=2, overdue=4, weighted=30.0, tardiness=30.0)
    refs = {baseline.candidate_key: "ref-baseline", graph.candidate_key: "ref-graph", third.candidate_key: "ref-third"}
    rows = [{"key": candidate.candidate_key, "candidate_ref": refs[candidate.candidate_key],
             "artifact": {"objective_name": candidate.objective_name, "score": list(candidate.score)}}
            for candidate in (baseline, graph, third)]

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
    assert basis["selected_candidate_ref"] == refs[graph.candidate_key]
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
