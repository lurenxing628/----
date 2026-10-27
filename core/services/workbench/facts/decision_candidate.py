"""Pure candidate cards shared by archive builders and decision readers."""

from .candidate_projection import business_candidate_fields
from .candidate_values import corrupt
from .decision_metrics import candidate_metrics
from .decision_selection import selection_roles


def project_candidate_summary(row, tasks, facts, batch_refs, basis, rows, delivery_items, *, operation_scope):
    artifact = row["artifact"]
    if row["status"] != "completed" or artifact.get("status") != row["status"] or artifact.get("sequence") != row["sequence"]:
        corrupt()
    coverage, values = candidate_metrics(row, tasks, facts, batch_refs,
                                         delivery_items=delivery_items, operation_scope=operation_scope)
    coverage["search"] = {"state": "complete", "completed_count": len(rows), "total_count": len(rows)}
    completeness = coverage["schedulable"]["state"]
    return {"candidate_ref": row["candidate_ref"], "label": artifact.get("label"), "kind": artifact.get("kind"),
            "status": "partial" if completeness == "partial" else row["status"], "persisted_status": row["status"],
            "task_count": row["task_count"], "completeness": completeness, "coverage": coverage, "metrics": values,
            "capabilities": {"view": True, "compare": True, "gantt": True,
                             "adoption_preview": True, "adopt": False},
            "selection_role": selection_roles(row, basis),
            **business_candidate_fields(artifact)}
