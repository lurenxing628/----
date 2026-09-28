"""Carry the chosen material policy into trial moves and adoption."""

import json
from datetime import datetime

from core.models.workbench_trial import issue, reject
from data.repositories.schedule_history_repo import ScheduleHistoryRepository


def plan_material_policy(conn, version):
    history = ScheduleHistoryRepository(conn).get_by_version(version)
    raw = history.result_summary if history else None
    if not raw:
        return {}
    try:
        summary = json.loads(raw)
    except (ValueError, TypeError):
        # Legacy history summaries were plain display text, with no run settings.
        return {}
    if not isinstance(summary, dict) or "material_policy" not in summary:
        return {}
    policy = summary["material_policy"]
    if (not isinstance(policy, dict) or type(policy.get("ready_check")) is not bool
            or policy.get("material_strategy") not in ("strict", "stage", "split")):
        reject("material_policy_invalid", "原计划的物料放行方式无效，请核对排产记录。")
    return policy


def run_policy(admission):
    capture = admission.get("source", {}).get("capture", {})
    settings = capture.get("input", admission.get("source", {}).get("material_policy", {}))
    return {"ready_check": settings.get("ready_check", True),
            "material_strategy": settings.get("material_strategy", "strict")}


def material_issues(admission, checks, row):
    policy = {**run_policy(admission), "end_date": row["current"]["end"][:10]}
    original = row["original"]
    problems, day = checks.operation_readiness(original["batch"], original["operation"], policy)
    result = [issue(item["code"], item["message"], row["task_ref"]) for item in problems]
    if day and datetime.fromisoformat(row["current"]["start"]) < datetime.fromisoformat(day):
        result.append(issue("before_material_date", "安排早于本序物料到齐日期，请后移至 " + day + " 或之后。", row["task_ref"]))
    return result
