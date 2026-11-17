"""Pure candidate cards shared by archive builders and decision readers."""

from .candidate_projection import business_candidate_fields
from .decision_metrics import candidate_metrics
from .decision_selection import selection_roles


def project_candidate_summary(row, tasks, facts, batch_refs, basis, delivery_items, *, operation_scope):
    """The decision card of a candidate this run just built; ``status`` is derived from its coverage."""
    artifact = row["artifact"]
    coverage, values = candidate_metrics(row, tasks, facts, batch_refs,
                                         delivery_items=delivery_items, operation_scope=operation_scope)
    completeness = coverage["schedulable"]["state"]
    return {"candidate_ref": row["candidate_ref"], "label": artifact["label"],
            "status": "partial" if completeness == "partial" else "completed",
            "task_count": row["task_count"], "completeness": completeness, "coverage": coverage, "metrics": values,
            "capabilities": {"view": True, "compare": True, "gantt": True,
                             "adoption_preview": True, "adopt": False},
            "selection_role": selection_roles(row, basis),
            **business_candidate_fields(artifact)}
