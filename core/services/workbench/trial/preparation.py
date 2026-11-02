"""Trial projections read the same saved requirement and changeover facts."""

from core.services.workbench.facts.changeovers import changeover_projection
from core.services.workbench.facts.operation_effort_evidence import archived_standard_effort, saved_operation_efforts
from core.services.workbench.facts.preparation_projection import (
    PREPARATION_METRIC_VERSION,
    preparation_delta,
    preparation_summary,
    project_operation_effort,
    public_preparation_metrics,
    public_preparation_roles,
)
from core.services.workbench.facts.zero_duration import point_event_dto

from .arrangements import same_arrangement
from .effort import retained_role


def _allocation(runtime, *, arranged, deferred=False, source):
    if source == "external":
        return "external"
    role = (runtime or {}).get("requirement_role")
    if role in ("retained", "execution", "completed"):
        return role
    if not arranged:
        return "deferred" if deferred else "unplanned"
    return "new_schedule" if role == "new_schedule" else "unknown"


def _side_effort(name, ref, context, records, evidence, admission, *, standard=None):
    op, execution = context["operation"], context["execution"]
    standard = archived_standard_effort(op, execution) if standard is None else standard
    current_execution = admission["execution"][ref]
    runtime = records.get(ref)
    if runtime is not None and runtime["op_id"] != op["id"]:
        from core.services.workbench.facts.candidate_values import corrupt

        corrupt()
    value = project_operation_effort(runtime, standard,
        allocation_state=_allocation(runtime, arranged=context["arranged"], deferred=context["deferred"], source=op["source"]),
        source=op["source"], execution=current_execution, evidence_source=evidence)
    if name == "after" and runtime is None and context["arranged"]:
        row = context["row"]
        held = row["original"].get("execution_anchor") is not None or same_arrangement(row["current"], row["original"]["arrangement"])
        role = retained_role(row, current_execution) if held else "new_schedule"
        value.update(requirement_role=role, allocation_state="external" if op["source"] == "external" else role)
    return value


def after_preparation_rows(admission, current_ledger, *, current_evidence, contexts):
    after = saved_operation_efforts(current_ledger)
    return [dict(_side_effort("after", ref, context, after, current_evidence, admission),
                 operation_ref=ref, arranged=context["arranged"])
            for ref, context in contexts.items()]


def preparation_projection(admission, current_ledger, *, current_evidence, contexts, before_efforts=None):
    """The immutable source and the explicit current ledger remain distinct."""
    source = admission["source"]
    before = saved_operation_efforts(source.get("operation_effort")) if before_efforts is None else before_efforts
    after = saved_operation_efforts(current_ledger)
    pairs, summary_rows = {}, {"before": [], "after": []}
    origin = source.get("identity")
    for ref, context in contexts.items():
        op, execution = context["operation"], context["execution"]
        standard = archived_standard_effort(op, execution)
        pair = {}
        for name, records, evidence in (("before", before, origin), ("after", after, current_evidence)):
            value = _side_effort(name, ref, context, records, evidence, admission, standard=standard)
            pair[name] = value
            summary_rows[name].append(dict(value, operation_ref=ref, arranged=context["arranged"]))
        pairs[ref] = pair
    summaries = {name: preparation_summary(values) for name, values in summary_rows.items()}
    return pairs, {"metric_version": PREPARATION_METRIC_VERSION, "scope": "full_admission",
        "before": public_preparation_metrics(summaries["before"]["metrics"]),
        "after": public_preparation_metrics(summaries["after"]["metrics"]),
        "deltas": {key: preparation_delta(summaries["after"]["metrics"][key], value)
                   for key, value in summaries["before"]["metrics"].items()},
        "role_totals": {name: public_preparation_roles(summary["role_totals"]) for name, summary in summaries.items()},
        "coverage": {name: summary["coverage"] for name, summary in summaries.items()}}


def trial_changeovers(rows, origin, *, start=None, end=None, next_operation_refs=None, after_only=False, trial_intervals):
    source = origin.admission["source"]
    types = source.get("operation_types") or {}
    slot_types = source["trial_operation_types"]
    machine_rows = (origin.facts.tables["Machines"].values() if origin.facts is not None
                    else origin.admission["facts"]["tables"]["Machines"])
    machines = {item["machine_id"]: item.get("name") for item in machine_rows}
    projected = {}
    sides = ("current",) if after_only else ("original", "current")
    for side in sides:
        tasks = []
        row_intervals = trial_intervals["original_by_row"] if side == "original" else trial_intervals["current_by_row"]
        side_intervals = trial_intervals["original_by_source_row"] if side == "original" else trial_intervals["current_by_row"]
        for row in rows:
            original = row["original"]
            arrangement = original["arrangement"] if side == "original" else row["current"]
            actual_types = slot_types if side == "current" and "operation_effort" in row["current"] else types
            kind = actual_types.get(row["operation_ref"], {})
            task = {"row_ref": row["source_row_ref"] if side == "original" else row["row_ref"], "operation_ref": row["operation_ref"],
                "source": original["operation"]["source"], "start": arrangement["start"], "end": arrangement["end"],
                "machine": {"ref": arrangement["machine_ref"], "label": machines.get(arrangement["machine_id"])},
                "process_type_ref": kind.get("ref"), "process_type_label": kind.get("label")}
            if task["start"] == task["end"]:
                span = row_intervals.get(row["row_ref"])
                if span is not None and span[0] == span[1]:
                    task.update(point_event_dto(span[0], span[1]))
            tasks.append(task)
        projected["before" if side == "original" else "after"] = changeover_projection(
            tasks, start=start, end=end, next_operation_refs=next_operation_refs, task_intervals=side_intervals)
    windowed = start is not None or end is not None
    return {"scope": "fixed_changeover_window" if windowed else "complete_trial",
            "metric_version": PREPARATION_METRIC_VERSION if windowed else "type_changeover_v1", **projected}


def apply_preparation(tasks, unplanned, pairs):
    for task in tasks + unplanned:
        task["operation_effort"] = pairs[task["operation_ref"]]


def apply_changeovers(comparison, common):
    comparison["changeover_common"] = common
    comparison["changeovers"] = common["after"]["count"]
    comparison["changeover_reason"] = "；".join(item["message"] for item in common["after"]["issues"]) or None
