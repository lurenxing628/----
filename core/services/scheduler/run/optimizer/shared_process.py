"""One factual process record for a shared optimizer run."""

from __future__ import annotations

from math import isfinite
from typing import Any, Dict, List

from .process_evidence import sample_elapsed_points

UNIFIED_PROCESS_VERSION = "unified-optimization-process-v1"


def score_scope_payload(scope: Any) -> Dict[str, Any]:
    return {
        "scheduled_operation_ids": sorted(scope.scheduled_operation_ids),
        "complete_batch_ids": sorted(scope.complete_batch_ids),
        "objective_scope": scope.objective_scope,
        "components_known": scope.components_known,
        "is_complete": scope.is_complete,
    }


def numeric_score(score: Any, *, components_known: bool) -> List[Any]:
    values = [value if isinstance(value, (int, float)) and isfinite(value) else None for value in score]
    if not components_known:
        values = values[:1] + [None] * max(len(values) - 1, 0)
    return values


def build_shared_process(search: Any, *, runtime_ms: int, stop_reason: str,
                         decode_stats: Dict[str, Any], budget_stats: Dict[str, Any]) -> Dict[str, Any]:
    """Sample target curves while total costs remain a single run fact."""
    scopes: Dict[str, Dict[str, Any]] = {}
    scope_refs: Dict[Any, str] = {}

    def scope_reference(scope: Any) -> str:
        if scope not in scope_refs:
            scope_ref = str(len(scopes) + 1)
            scope_refs[scope] = scope_ref
            scopes[scope_ref] = score_scope_payload(scope)
        return scope_refs[scope]

    # Actual event order establishes the first occurrence of each scope; the other fields are
    # referenced as they are, without materializing full scope members for every event. The
    # record is built once after the search stops and nothing mutates the search facts afterwards.
    events = []
    for row in search.events:
        event = {key: value for key, value in row.items() if key not in ("score_scope", "evaluations")}
        if "score_scope" in row:
            scope = row["score_scope"]
            event["scope_ref"] = scope_reference(scope)
            event["evaluations"] = {
                objective: {
                    **evaluation,
                    "field_order": list(evaluation["field_order"]),
                    "score": numeric_score(evaluation["score"], components_known=scope.components_known),
                }
                for objective, evaluation in row.get("evaluations", {}).items()
            }
        events.append(event)
    event_by_id = {event["event_id"]: event for event in events}

    targets = {}
    improvement_counts = search.archive.improvement_counts
    for objective in search.archive.target_objectives:
        points, previous_scope, segment = [], None, 0
        first_known, first_complete = False, False
        for row in search.trajectories[objective]:
            scope = row["score_scope"]
            if previous_scope is not None and scope != previous_scope:
                segment += 1
            previous_scope = scope
            flags = []
            if scope.components_known and not first_known:
                flags.append("first_valid")
                first_known = True
            if scope.is_complete and not first_complete:
                flags.append("first_expected_complete")
                first_complete = True
            source = event_by_id.get(row["source_event_id"])
            improvement_key = "improved_objectives" if scope.is_complete else "partial_group_improved_objectives"
            scope_ref = scope_reference(scope)
            if (source is not None and source["event_type"] == "archive_observation" and source["verified"] is True
                    and source["entry_id"] == row["entry_id"] and source["elapsed_ms"] == row["elapsed_ms"]
                    and source.get("scope_ref") == scope_ref and objective in source.get(improvement_key, ())):
                flags.append("strict_improvement")
            point = {key: value for key, value in row.items() if key not in ("score_scope", "score")}
            point.update(scope_ref=scope_ref,
                         score=numeric_score(row["score"], components_known=scope.components_known),
                         segment=segment, flags=flags)
            points.append(point)
        improvements = [point["elapsed_ms"] for point in points if "strict_improvement" in point["flags"]]
        selected_id = search.selected_entry(objective)
        if selected_id is not None:
            selected = search.archive.entry(selected_id)
            evaluation = selected.evaluations[objective]
            scope = selected.score_scope
            if previous_scope is not None and scope != previous_scope:
                segment += 1
            points.append({
                "elapsed_ms": runtime_ms, "entry_id": selected_id,
                "source_event_id": search.evidence_event_ids.get(selected_id),
                "search_objective": selected.evidence_origin.get("search_objective"),
                "origin": selected.evidence_origin.get("origin"),
                "score": numeric_score(evaluation.score, components_known=scope.components_known),
                "field_order": list(evaluation.field_order), "scope_ref": scope_reference(scope),
                "segment": segment, "flags": ["final"],
            })
        sampled, sampling = sample_elapsed_points(points, elapsed_ms=runtime_ms, limit=200)
        targets[objective] = {
            **budget_stats["objectives"][objective],
            "archive_improvement_count": improvement_counts[objective],
            "first_improvement_elapsed_ms": improvements[0] if improvements else None,
            "last_improvement_elapsed_ms": improvements[-1] if improvements else None,
            "best_entry_id": selected_id, "points": sampled, "sampling": sampling,
        }
    return {
        "version": UNIFIED_PROCESS_VERSION, "clock": "shared_monotonic", "elapsed_ms": runtime_ms,
        "stop_reason": stop_reason, "primary_objective": search.archive.primary_objective,
        "target_objectives": list(search.archive.target_objectives), "counts": dict(decode_stats),
        "budget": budget_stats, "events": events, "actions": search.actions,
        "bridges": search.bridges, "targets": targets, "scopes": scopes,
    }


__all__ = ["UNIFIED_PROCESS_VERSION", "build_shared_process", "score_scope_payload"]
