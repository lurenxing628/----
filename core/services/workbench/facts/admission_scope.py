"""The accepted workload labels and counts, shared by journal and saved models."""

from core.models.objective import objective_choice_labels
from core.models.workbench_command import canonical_json

from .candidate_facts import _entity_refs, _index, _table
from .candidate_values import gap, text
from .run_history_projection import scope_summary


def project_admitted_scope(settings, archive, *, tables=None, entity_refs=None, summary=None):
    summary = scope_summary(canonical_json(settings)) if summary is None else summary
    refs = _entity_refs(archive) if entity_refs is None else entity_refs
    batches = _index(_table(archive, "Batches"), "batch_id") if tables is None else tables["Batches"]
    parts = _index(_table(archive, "Parts"), "part_no") if tables is None else tables["Parts"]
    batch_ids = {ref: key for (kind, key), ref in refs.items() if kind == "batch"}
    gaps, selected = list(summary["data_gaps"]), []
    for ref in settings.get("batch_refs", []) if summary["batch_count"] is not None else []:
        batch = batches.get(batch_ids.get(ref), {})
        prefix = "batches." + ref + "."
        batch_id = text(batch.get("batch_id"), prefix + "batch_id", gaps)
        part_no = text(batch.get("part_no"), prefix + "part_no", gaps)
        part = parts.get(part_no, {})
        selected.append({"batch_ref": ref, "batch_id": batch_id, "part_no": part_no,
                         "part_label": text(part.get("part_name"), prefix + "part_label", gaps)})
    operations = (_table(archive, "BatchOperations") if tables is None else
                  list(tables["BatchOperations"].values()) if "BatchOperations" in archive["tables"] else None)
    complete_scope = summary["batch_count"] is not None and all(item["batch_id"] is not None for item in selected)
    operation_count = None
    if complete_scope and operations is not None:
        selected_ids = {item["batch_id"] for item in selected}
        operation_count = sum(item.get("batch_id") in selected_ids for item in operations)
    else:
        gaps.append(gap("operation_count"))
    config = _index(_table(archive, "ScheduleConfig"), "config_key")
    objective = text(config.get("objective", {}).get("config_value"), "objective", gaps)
    labels = objective_choice_labels()
    if objective is not None and objective not in labels:
        gaps.append(gap("objective", "invalid_stored_value"))
    return {**summary, "data_gaps": gaps, "operation_count": operation_count, "batches": selected,
            "objective": objective, "objective_label": labels.get(objective) if objective is not None else None}
