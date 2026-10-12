"""Whole-admission descriptive metrics; unknown evidence is never counted as zero."""

from .workbench_run_baseline import baseline_reason
from .workbench_run_candidate import reject


def metric(value, known, unknown, total, reason=None):
    return {"value": value, "known_subtotal": known, "unknown_count": unknown,
            "total_count": total, "reason": reason if unknown else None}


def delivery_metrics(rows, summary):
    unknown, total = summary["unknown_count"], summary["batch_count"]
    reason = (baseline_reason("no_admission_baseline") if rows and all("no_admission_baseline" in row["issues"] for row in rows)
              else {"code": "delivery_evidence_incomplete", "message": "排产时有部分批次的安排或交期资料不全，这里的小计不包含它们。"})
    return {
        "overdue_count": metric(summary["overdue_count"], summary["known_overdue_count"], unknown, total, reason),
        "total_tardiness_hours": metric(summary["total_tardiness_hours"],
            round(sum(row["delay_hours"] for row in rows if row["delay_hours"] is not None), 6), unknown, total, reason),
    }


def operation_change(row):
    if row["status"] == "newly_scheduled":
        return True, False, []
    if row["status"] == "unscheduled":
        return bool(row["baseline_segments"]), False, []
    if not row["comparison_available"]:
        reasons = [r for r in row["reasons"] if r["code"] != "execution_affected"]
        return None, None, reasons or [baseline_reason("no_comparable_operations")]
    delta, candidate = row["delta"], row["candidate"]
    machine = delta["machine_changed"]
    reasons = []
    if machine is None or delta["operator_changed"] is None:
        reasons.append(baseline_reason("resource_identity_unavailable"))
    baseline = row["baseline_segments"][0]
    if baseline["source"] is None:
        reasons.append(_stored_reason(baseline, "source", "historical_source_unavailable"))
    supplier_relevant = "external" in (candidate["source"], baseline["source"])
    if supplier_relevant and delta["supplier_changed"] is None:
        reason = _stored_reason(baseline, "supplier", "historical_supplier_not_recorded")
        if reason not in reasons:
            reasons.append(reason)
    source_changed = baseline["source"] is not None and baseline["source"] != candidate["source"]
    changed = (source_changed or machine is True or delta["operator_changed"] is True
               or supplier_relevant and delta["supplier_changed"] is True
               or delta["start_hours"] != 0 or delta["end_hours"] != 0)
    return True if changed else None if reasons else False, machine, reasons


def _stored_reason(side, field, default):
    saved = next((row for row in side["data_gaps"] if row["field"] == field), None)
    return {"code": saved["code"], "message": saved["message"]} if saved else baseline_reason(default)


def _admission_operation_rows(baseline, batch_refs):
    rows = [row for row in baseline["comparisons"] if row["selected_at_admission"]]
    refs = [row["operation_ref"] for row in rows]
    if (len(set(refs)) != len(refs) or not baseline["rows_complete"]
            or baseline["operation_count"] != baseline["full_operation_count"]
            or any(row["batch_ref"] not in batch_refs for row in rows)):
        reject("candidate_analysis_incomplete", "整份候选工序身份不完整，未从可见安排估算调整数量。", 500)
    return rows, refs


def operation_metrics(baseline, batch_refs):
    rows, refs = _admission_operation_rows(baseline, batch_refs)
    changed, machines, unknown, machine_unknown, issues = [], [], [], [], []
    for row in rows:
        change, machine, reasons = operation_change(row)
        ref = row["operation_ref"]
        if change is None:
            unknown.append(ref)
        elif change:
            changed.append(ref)
        if machine is None:
            machine_unknown.append(ref)
        elif machine:
            machines.append(ref)
        if reasons:
            issues.append({"operation_ref": ref, "reasons": reasons})
    reason = {"code": "operation_comparison_incomplete", "message": "部分工序的初始安排或资源编号缺失，调整数量暂无法完整统计。"}
    metrics = {
        "changed_operation_count": metric(None if unknown else len(changed), len(changed), len(unknown), len(rows), reason),
        "machine_change_count": metric(None if machine_unknown else len(machines), len(machines), len(machine_unknown), len(rows), reason),
    }
    return metrics, {"operation_refs": refs, "changed_operation_refs": changed, "machine_changed_operation_refs": machines,
                     "unknown_operation_refs": unknown, "machine_unknown_operation_refs": machine_unknown, "issues": issues}


def delivery_deltas(before, after):
    return {key: None if before[key]["value"] is None or after[key]["value"] is None
            else round(after[key]["value"] - before[key]["value"], 6) for key in before}
