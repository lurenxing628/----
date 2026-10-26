"""The accepted workload labels and counts, shared by journal and saved models."""

from core.models.objective import objective_choice_labels

from .candidate_facts import index_rows
from .candidate_values import gap, text


def project_admitted_scope(settings, facts, *, summary):
    """facts is the run's GenerationFacts; summary is its scope_summary of settings."""
    batches, parts = facts.tables["Batches"], facts.tables["Parts"]
    batch_ids = {ref: key for (kind, key), ref in facts.entity_refs.items() if kind == "batch"}
    gaps, selected = list(summary["data_gaps"]), []
    for ref in settings.get("batch_refs", []) if summary["batch_count"] is not None else []:
        batch = batches.get(batch_ids.get(ref), {})
        prefix = "batches." + ref + "."
        batch_id = text(batch.get("batch_id"), prefix + "batch_id", gaps)
        part_no = text(batch.get("part_no"), prefix + "part_no", gaps)
        part = parts.get(part_no, {})
        selected.append({"batch_ref": ref, "batch_id": batch_id, "part_no": part_no,
                         "part_label": text(part.get("part_name"), prefix + "part_label", gaps)})
    operations = facts.tables["BatchOperations"].values() if "BatchOperations" in facts.archive["tables"] else None
    complete_scope = summary["batch_count"] is not None and all(item["batch_id"] is not None for item in selected)
    operation_count = None
    if complete_scope and operations is not None:
        selected_ids = {item["batch_id"] for item in selected}
        operation_count = sum(item.get("batch_id") in selected_ids for item in operations)
    else:
        gaps.append(gap("operation_count"))
    config = index_rows(facts.table("ScheduleConfig"), "config_key")
    objective = text(config.get("objective", {}).get("config_value"), "objective", gaps)
    labels = objective_choice_labels()
    if objective is not None and objective not in labels:
        gaps.append(gap("objective", "invalid_stored_value"))
    return {**summary, "data_gaps": gaps, "operation_count": operation_count, "batches": selected,
            "objective": objective, "objective_label": labels.get(objective) if objective is not None else None}
