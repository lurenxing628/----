"""Pure views of one saved shared-optimization process and its actual origins."""

from core.models.objective import best_score_schema, comparison_metric_key, objective_choice_labels
from core.services.scheduler.run.optimizer.shared_process import UNIFIED_PROCESS_VERSION

from .candidate_artifact import scoring_scope_record
from .candidate_values import corrupt

PROCESS_CANDIDATE_FIELDS = ("candidate_ref", "label", "status", "representative_objectives", "origin",
                     "first_found_elapsed_ms", "search_evidence_ref")
_ACTION_COUNTERS = ("evaluation_count", "verified_evaluation_count", "new_decisions", "reused_decisions")


def _candidate(row):
    """One candidate's catalog card fields; the saved catalog (``candidate_summary``) carries every one of them."""
    return {key: row[key] for key in PROCESS_CANDIDATE_FIELDS}


def _unit(key):
    return "工序" if key == "failed_ops" else "批次" if key == "overdue_count" else "次" if key == "changeover_count" else "小时" if key.endswith("_hours") else None


def _objective(name):
    """A target direction's business label and its scoring fields; unknown directions are corrupt."""
    labels = objective_choice_labels()
    if name not in labels:
        corrupt()
    primary = comparison_metric_key(name)
    fields = [{"index": row["index"], "key": row["key"],
               "label": "算法工种切换次数" if row["key"] == "changeover_count" else row["label"],
               "unit": _unit(row["key"]), "direction": "lower"} for row in best_score_schema(name)]
    field = next(row for row in fields if row["key"] == primary)
    return {"name": name, "label": "最少算法工种切换次数" if name == "min_changeover" else labels[name],
            "primary_metric_key": primary, "primary_metric_label": field["label"], "unit": field["unit"], "score_fields": fields}


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


def project_unified_process(process, *, objective, candidate, candidates=()):
    """Project one resolved target direction of parsed saved facts with scalar scope counts; perform no reads."""
    objectives = [_objective(name) for name in process["target_objectives"]]
    descriptor = next(row for row in objectives if row["name"] == objective)
    scopes = {scope_ref: scoring_scope_record(scope, scheduled=scope["scheduled_operation_refs"],
                                              complete=scope["complete_batch_refs"])
              for scope_ref, scope in process["scopes"].items()}
    events = {event["event_id"]: event for event in process["events"]}
    first_complete = [event["elapsed_ms"] for event in events.values()
                      if event["event_type"] == "archive_observation" and event["verified"] is True
                      and event.get("scope_ref") is not None and scopes[event["scope_ref"]]["is_complete"] is True]
    target = process["targets"][objective]
    if len(target["points"]) > 200:
        corrupt()
    points = []
    key = descriptor["primary_metric_key"]
    for point in target["points"]:
        source = events.get(point["source_event_id"])
        if source is None:
            corrupt()
        field_order = point["field_order"]
        if key not in field_order or len(field_order) != len(point["score"]):
            corrupt()
        points.append({**point, "phase": source["phase"], "verified": source["verified"],
                       "primary_value": point["score"][field_order.index(key)]})
    actions = [action for action in process["actions"] if action["search_objective"] == objective]
    current = _candidate(candidate)
    # The saved evidence names a source event only when the search recorded one for this entry; a named event
    # missing from the saved process is corrupt, as for the progress points above.
    event_id = current["search_evidence_ref"]["source_event_id"]
    if event_id is not None and event_id not in events:
        corrupt()
    source_event = None if event_id is None else events[event_id]
    return {"process_version": UNIFIED_PROCESS_VERSION,
            "summary": {"elapsed_ms": process["elapsed_ms"],
                        "first_complete_elapsed_ms": min(first_complete) if first_complete else None,
                        "first_improvement_elapsed_ms": target["first_improvement_elapsed_ms"],
                        "last_improvement_elapsed_ms": target["last_improvement_elapsed_ms"]},
            "counts": process["counts"], "budget": process["budget"], "stop_reason": process["stop_reason"],
            "bridges": process["bridges"], "objectives": objectives, "selected_objective": descriptor,
            "progress": {"points": points, "sampling": target["sampling"]}, "scopes": scopes,
            "actions": actions, "stages": _stages(actions, process["budget"]["objectives"][objective]["phase_elapsed_seconds"]),
            "candidate": current, "candidates": [_candidate(row) for row in candidates], "source_event": source_event}


__all__ = ["PROCESS_CANDIDATE_FIELDS", "project_unified_process"]
