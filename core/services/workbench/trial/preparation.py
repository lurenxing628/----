"""Trial projections read the same saved requirement and changeover facts."""

from core.services.workbench.facts.candidate_facts import GenerationFacts
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
from core.services.workbench.facts.trial_origin import operation_contexts
from core.services.workbench.facts.zero_duration import point_event_dto
from core.services.workbench.facts.zero_duration_evidence import trial_point_evidence

from .arrangements import same_arrangement
from .effort import operation_types, retained_role


def _allocation(runtime, *, arranged, deferred=False, source=None):
    if source == "external":
        return "external"
    role = (runtime or {}).get("requirement_role")
    if role in ("retained", "execution", "completed"):
        return role
    if not arranged:
        return "deferred" if deferred else "unplanned"
    return "new_schedule" if role == "new_schedule" else "unknown"


def preparation_projection(rows, admission, current_ledger, *, current_evidence=None, contexts=None):
    """The immutable source and the explicit current ledger remain distinct."""
    source = admission["source"]
    before = saved_operation_efforts(source.get("operation_effort"))
    after = saved_operation_efforts(current_ledger)
    contexts = operation_contexts(rows, admission) if contexts is None else contexts
    pairs, summary_rows = {}, {"before": [], "after": []}
    origin = source.get("identity")
    for ref, context in contexts.items():
        op, execution = context["operation"], context["execution"]
        standard = archived_standard_effort(op, execution)
        current_execution = admission["execution"].get(ref, {})
        pair = {}
        for name, records, evidence in (("before", before, origin), ("after", after, current_evidence or origin)):
            runtime = records.get(ref)
            if runtime is not None and runtime["op_id"] != op["id"]:
                from core.services.workbench.facts.candidate_values import corrupt

                corrupt()
            value = project_operation_effort(runtime, standard,
                allocation_state=_allocation(runtime, arranged=context["arranged"], deferred=context.get("deferred", False), source=op["source"]),
                source=op["source"], execution=current_execution, evidence_source=evidence)
            if name == "after" and runtime is None and context["arranged"]:
                row = context["row"]
                held = row["original"].get("execution_anchor") is not None or same_arrangement(row["current"], row["original"]["arrangement"])
                role = retained_role(row, admission) if held else "new_schedule"
                value.update(requirement_role=role, allocation_state="external" if op["source"] == "external" else role,
                    execution_target_quantity=current_execution.get("target_quantity"),
                    execution_quantity_basis=current_execution.get("target_basis", "unknown"),
                    remaining_quantity=current_execution.get("remaining_quantity"))
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


def trial_changeovers(rows, admission, *, start=None, end=None, next_operation_refs=None):
    source = admission["source"]
    types = source.get("operation_types") or {}
    slot_types = source.get("trial_operation_types")
    if slot_types is None:
        tables = admission["facts"]["tables"]
        refs = {(item["kind"], item["entity_key"]): item["ref"] for item in tables["WorkbenchEntityRefs"] if item["active"] == 1}
        slot_types = operation_types(rows, refs, {item["op_type_id"]: item for item in tables["OpTypes"]})
    machine_rows = (GenerationFacts(source["capture"]).tables["Machines"].values() if "capture" in source
                    else admission["facts"]["tables"]["Machines"])
    machines = {item["machine_id"]: item.get("name") for item in machine_rows}
    projected = {}
    for side in ("original", "current"):
        tasks = []
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
                witness = trial_point_evidence(original, arrangement)
                task.update(point_event_dto(witness.at, witness.at))
            tasks.append(task)
        projected["before" if side == "original" else "after"] = changeover_projection(
            tasks, start=start, end=end, next_operation_refs=next_operation_refs)
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
