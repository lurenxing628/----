"""Risk classification consumes the execution ledger, never another report store."""

from core.services.workbench.dashboard_projection import category, observation
from core.services.workbench.preflight_checks import number
from core.services.workbench.review_values import minutes


def _hours(projection, operation):
    reports = projection["reports"]
    target = projection["target_quantity"]
    quota = operation["unit_hours"] * target if number(operation["unit_hours"], positive=True) and number(target, positive=True) else None
    complete = (projection["completion_basis"] == "complete_reports" and projection["records_complete"]
                and projection["data_quality"] == "complete" and reports
                and all(number(row["effective_processing_hours"]) for row in reports))
    total = sum(row["effective_processing_hours"] for row in reports) if complete else None
    return {"effective_processing_hours": total, "quota_processing_hours": quota,
            "overrun": total > quota * 1.2 if total is not None and quota is not None else None,
            "basis": "complete_report_processing_hours_vs_operation_unit_hours_times_target",
            "setup_or_elapsed_hours_included": False}


def _risk_codes(task, projection, hours, now):
    late = minutes(task["end"], projection["confirmed_finish"])
    missing = task["start"] <= now.isoformat(timespec="seconds") and projection["first_actual_start"] is None and projection["execution_state"] != "complete"
    codes = []
    if missing:
        codes.append("feedback_pending")
    if late is not None and late > 10:
        codes.append("finish_late")
    if projection["execution_state"] in ("paused", "exception"):
        codes.append("execution_" + projection["execution_state"])
    if hours["overrun"]:
        codes.append("processing_hours_overrun")
    return codes, missing, late


def _source(task, p, hours, codes, late):
    return {"kind": "execution_projection", "plan_ref": task["plan_ref"], "task_ref": task["task_ref"],
                  "operation_ref": task["operation_ref"], "batch_id": task["batch_id"], "planned_start": task["start"], "planned_end": task["end"],
                  "execution_state": p["execution_state"], "completion_basis": p["completion_basis"],
                  "confirmed_finish": p["confirmed_finish"], "first_actual_start": p["first_actual_start"],
                  "data_quality": p["data_quality"], "data_gaps": p["data_gaps"], "hours": hours,
                  "finish_deviation_minutes": late, "risk_codes": codes,
                  "report_refs": [row["report_ref"] for row in p["reports"]],
                  "legacy_fact_refs": [row["legacy_fact_ref"] for row in p["legacy_facts"]]}


def _operation(facts, task, raw_task):
    ref = task["operation_ref"]
    p, operation = facts.execution[ref], facts.execution_facts["operations"][ref]
    hours = _hours(p, operation)
    codes, missing, late = _risk_codes(task, p, hours, facts.now)
    uncertain = p["data_quality"] == "invalid" or bool(p["reports"] or p["legacy_facts"]) and hours["overrun"] is None
    active = True if codes else None if uncertain else False
    source = _source(task, p, hours, codes, late)
    item = observation("actual", task["task_ref"], task["batch_id"] + " · " + task["process_label"], source,
                                 active, codes[0] if codes else "execution_unknown" if uncertain else "no_deviation",
                                 "现场还没反馈，不等于没干。" if missing else "报工记录显示有偏差或异常。" if codes else
                                 "报工或有效工时的数据不够，还评估不全。" if uncertain else "已读取报工记录，这次检查没发现偏差。",
                                 {"task": raw_task, "operation": operation, "projection": p,
                                  "reports": facts.execution_facts["reports"].get(ref),
                                  "legacy": facts.execution_facts["legacy"].get(ref),
                                  "legacy_source": {"hash": facts.execution_facts["legacy_source"]["hashes"].get(ref),
                                                    "changes": facts.execution_facts["legacy_source"]["changes"].get(ref)}})
    return item, uncertain


def actual(facts):
    if facts.plan_state != "loaded":
        return [], category(facts.plan_state, issues=facts.plan_issues)
    if facts.execution is None:
        return [], category("unavailable", issues=facts.execution_issues)
    items, unknown = [], 0
    for task, raw_task in zip(facts.tasks, facts.task_rows):
        item, uncertain = _operation(facts, task, raw_task)
        items.append(item)
        unknown += uncertain
    return items, category("loaded" if items else "no_data", assessed=len(items) - unknown, unknown=unknown)
