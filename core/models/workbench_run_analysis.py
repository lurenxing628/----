"""Whole-admission descriptive metrics; unknown evidence is never counted as zero."""

from .workbench_run_baseline import baseline_reason
from .workbench_run_candidate import reject


def metric(value, known, unknown, total, reason=None):
    return {"value": value, "known_subtotal": known, "unknown_count": unknown,
            "total_count": total, "reason": reason if unknown else None}


def delivery_metrics(rows, summary):
    unknown, total = summary["unknown_count"], summary["batch_count"]
    reason = {"code": "delivery_evidence_incomplete", "message": "排产时有部分批次的安排或交期资料不全，这里的小计不包含它们。"}
    return {
        "overdue_count": metric(summary["overdue_count"], summary["known_overdue_count"], unknown, total, reason),
        "total_tardiness_hours": metric(summary["total_tardiness_hours"],
            round(sum(row["delay_hours"] for row in rows if row["delay_hours"] is not None), 6), unknown, total, reason),
    }


def _operation_change(row):
    if not row["comparison_available"]:
        reasons = [r for r in row["reasons"] if r["code"] != "execution_affected"]
        return None, None, reasons or [baseline_reason("no_comparable_operations")]
    delta, candidate = row["delta"], row["candidate"]
    machine = delta["machine_changed"]
    if machine is None or delta["operator_changed"] is None:
        return None, machine, [baseline_reason("resource_identity_unavailable")]
    if candidate["source"] == "external":
        return None, machine, [baseline_reason("historical_supplier_not_recorded")]
    changed = machine or delta["operator_changed"] or delta["start_hours"] != 0 or delta["end_hours"] != 0
    return changed, machine, []


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
        change, machine, reasons = _operation_change(row)
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
    reason = {"code": "operation_comparison_incomplete", "message": "部分工序缺少可一一核对的初始安排或资源永久身份；已知小计不代表完整调整数。"}
    metrics = {
        "changed_operation_count": metric(None if unknown else len(changed), len(changed), len(unknown), len(rows), reason),
        "machine_change_count": metric(None if machine_unknown else len(machines), len(machines), len(machine_unknown), len(rows), reason),
    }
    return metrics, {"operation_refs": refs, "changed_operation_refs": changed, "machine_changed_operation_refs": machines,
                     "unknown_operation_refs": unknown, "machine_unknown_operation_refs": machine_unknown, "issues": issues}


def delivery_deltas(before, after):
    return {key: None if before[key]["value"] is None or after[key]["value"] is None
            else round(after[key]["value"] - before[key]["value"], 6) for key in before}
