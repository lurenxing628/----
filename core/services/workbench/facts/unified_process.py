"""Pure views of one saved shared-optimization process and its actual origins."""

from core.models.workbench_run_candidate import reject
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION

from .candidate_process import _objective
from .candidate_values import corrupt

PROCESS_CANDIDATE_FIELDS = ("candidate_ref", "label", "status", "representative_objectives", "origin",
                     "first_found_elapsed_ms", "search_evidence_ref")
_SCOPE_FIELDS = ("scheduled_operation_refs", "complete_batch_refs", "objective_scope", "components_known", "is_complete")
_ACTION_COUNTERS = ("evaluation_count", "verified_evaluation_count", "new_decisions", "reused_decisions")


def _candidate(row):
    return {key: row.get(key) for key in PROCESS_CANDIDATE_FIELDS} if row is not None else None


def _stages(actions, phase_seconds):
    grouped = {phase: [] for phase in phase_seconds}
    for action in actions:
        grouped.setdefault(action["phase"], []).append(action)
    return [{"phase": phase,
             "start_elapsed_ms": min(action["started_elapsed_ms"] for action in rows) if rows else None,
             "end_elapsed_ms": max(action["finished_elapsed_ms"] for action in rows) if rows else None,
             "elapsed_ms": phase_seconds[phase] * 1000 if phase in phase_seconds else None,
             "action_count": len(rows),
             **{key: sum(action[key] for action in rows) for key in _ACTION_COUNTERS}}
            for phase, rows in grouped.items()]


def project_unified_process(process, *, objective=None, candidate=None, candidates=()):
    """Consume parsed saved facts with permanent scope members; perform no reads."""
    if process["version"] != UNIFIED_PROCESS_VERSION:
        corrupt()
    selected = process["primary_objective"] if objective is None else objective
    if selected not in process["target_objectives"]:
        reject("invalid_input", "请选择本次排产的优化方向。", 422)
    objectives = [_objective({"objective_name": name}, {}, {}) for name in process["target_objectives"]]
    if any(row["primary_metric_key"] is None for row in objectives):
        corrupt()
    descriptor = next(row for row in objectives if row["name"] == selected)
    scopes = {scope_ref: {key: scope[key] for key in _SCOPE_FIELDS} for scope_ref, scope in process["scopes"].items()}
    events = {event["event_id"]: event for event in process["events"]}
    first_complete = [event["elapsed_ms"] for event in events.values()
                      if event["event_type"] == "archive_observation" and event["verified"] is True
                      and event.get("scope_ref") is not None and scopes[event["scope_ref"]]["is_complete"] is True]
    target = process["targets"][selected]
    if len(target["points"]) > 200:
        corrupt()
    points = []
    for point in target["points"]:
        source = events.get(point["source_event_id"])
        if source is None:
            corrupt()
        field_order = point["field_order"]
        key = descriptor["primary_metric_key"]
        if key not in field_order or len(field_order) != len(point["score"]):
            corrupt()
        points.append({**point, "phase": source["phase"], "verified": source["verified"],
                       "primary_value": point["score"][field_order.index(key)]})
    actions = [action for action in process["actions"] if action["search_objective"] == selected]
    current = _candidate(candidate)
    evidence = current["search_evidence_ref"] if current is not None else None
    source_event = events.get(evidence["source_event_id"]) if evidence is not None else None
    return {"process_version": UNIFIED_PROCESS_VERSION,
            "summary": {"elapsed_ms": process["elapsed_ms"],
                        "first_complete_elapsed_ms": min(first_complete) if first_complete else None,
                        "first_improvement_elapsed_ms": target["first_improvement_elapsed_ms"],
                        "last_improvement_elapsed_ms": target["last_improvement_elapsed_ms"]},
            "counts": process["counts"], "budget": process["budget"], "stop_reason": process["stop_reason"],
            "bridges": process["bridges"], "objectives": objectives, "selected_objective": descriptor,
            "progress": {"points": points, "sampling": target["sampling"]}, "scopes": scopes,
            "actions": actions, "stages": _stages(actions, process["budget"]["objectives"][selected]["phase_elapsed_seconds"]),
            "candidate": current, "candidates": [_candidate(row) for row in candidates], "source_event": source_event}


__all__ = ["PROCESS_CANDIDATE_FIELDS", "project_unified_process"]
