"""Pure candidate cards shared by archive builders and decision readers."""

from .candidate_projection import business_candidate_fields
from .candidate_values import corrupt
from .decision_metrics import candidate_metrics
from .decision_selection import selection_roles


def project_candidate_summary(row, tasks, facts, capture, disposition, batch_refs, basis, rows, delivery_items):
    artifact = row["artifact"]
    if artifact.get("status") != row["status"] or artifact.get("sequence") != row["sequence"]:
        corrupt()
    coverage, values = candidate_metrics(row, tasks, facts, capture["input"], disposition, batch_refs, delivery_items=delivery_items)
    completed = sum(candidate["status"] == "completed" for candidate in rows)
    coverage["search"] = {"state": "complete" if completed == len(rows) else "partial", "completed_count": completed,
                          "failed_count": sum(candidate["status"] == "failed" for candidate in rows),
                          "skipped_count": sum(candidate["status"] == "skipped" for candidate in rows), "total_count": len(rows)}
    state = coverage["schedulable"]["state"]
    completeness = "no_result" if row["status"] != "completed" else "unknown" if state == "unavailable" else state
    reused = artifact.get("reused_from_candidate_key")
    return {"candidate_ref": row["candidate_ref"], "label": artifact.get("label"), "kind": artifact.get("kind"),
            "status": "partial" if completeness == "partial" else row["status"], "persisted_status": row["status"],
            "task_count": row["task_count"], "completeness": completeness, "coverage": coverage, "metrics": values,
            "capabilities": {"view": True, "compare": row["status"] == "completed", "gantt": row["status"] == "completed",
                             "adoption_preview": row["status"] == "completed", "adopt": False},
            "selection_role": selection_roles(row, basis),
            "equivalent_source_ref": next((item["candidate_ref"] for item in rows if item["artifact"].get("candidate_key") == reused), None),
            "source": {**{key: artifact.get(key) for key in ("algo_mode", "used_strategy", "dispatch_mode", "dispatch_rule", "failure_reason")},
                       "reason": _candidate_reason(row)}, **business_candidate_fields(artifact)}


def _candidate_reason(row):
    if row["status"] == "completed":
        return None
    reason = row["artifact"].get("failure_reason")
    if reason == "candidate_time_budget_reached":
        return {"code": reason, "message": "本次计算时间预算已用完，该候选已跳过。"}
    if type(reason) is str and reason.strip():
        return {"code": "candidate_" + row["status"], "message": reason}
    return {"code": "candidate_reason_missing", "message": "排产存档缺少该候选的" + ("失败" if row["status"] == "failed" else "跳过") + "原因，请到排产记录核对。"}
