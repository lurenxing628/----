"""Public candidate summaries from persisted artifacts, without inferred costs."""

from core.models.workbench_run_candidate import blocked_reasons, read_capabilities, reference

from .run_candidate_values import corrupt, gap, number, text

_METRICS = ("overdue_count", "total_tardiness_hours", "makespan_hours", "changeover_count",
            "weighted_tardiness_hours", "machine_used_count", "operator_used_count",
            "machine_busy_hours_total", "operator_busy_hours_total", "machine_util_avg", "operator_util_avg")


def dispositions(receipt):
    value = None if receipt is None else receipt.get("dispositions")
    if value is None:
        return None
    if type(value) is not list:
        corrupt()
    result, ids = {}, set()
    for row in value:
        if type(row) is not dict:
            corrupt()
        ref, op = reference(row.get("operation_ref"), stored=True), row.get("op_id")
        if ref in result or type(op) is not int or op <= 0 or op in ids:
            corrupt()
        if row.get("status") not in ("eligible", "auto_assign_required", "protected", "skipped"):
            corrupt()
        result[ref] = row
        ids.add(op)
    return result


def validate_manifest(run, rows, receipt):
    if receipt is None:
        if rows:
            corrupt()
        return
    expected = receipt.get("candidates")
    if type(expected) is not list or len(expected) != len(rows):
        corrupt()
    index = {}
    for row in expected:
        if type(row) is not dict or row.get("candidate_ref") in index:
            corrupt()
        index[row.get("candidate_ref")] = row
    for row in rows:
        item = index.get(row["candidate_ref"])
        if item is None or item.get("task_count") != row["task_count"] or item.get("status") != row["status"]:
            corrupt()
    if run["state"] in ("complete", "partial") and (not rows or receipt.get("result_persisted") is not True):
        corrupt()


def _scheduled_values(payload, row):
    if type(payload.get("scheduled_op_ids")) is not list:
        corrupt()
    values = payload["scheduled_op_ids"]
    if any(type(value) is not int or value <= 0 for value in values) or len(set(values)) != len(values):
        corrupt()
    if len(values) != row["task_count"] or payload.get("out_of_scope_op_ids") or payload.get("validation_errors"):
        corrupt()
    return values


def _check_scheduled_rows(scheduled, values):
    if type(scheduled) is not list or any(type(item) is not dict or type(item.get("op_id")) is not int for item in scheduled):
        corrupt()
    if len(scheduled) != len(values) or {item["op_id"] for item in scheduled} != set(values):
        corrupt()


def scheduled_ids(row):
    payload = row["artifact"].get("validated_payload")
    if payload is None:
        return None
    if type(payload) is not dict:
        corrupt()
    values = _scheduled_values(payload, row)
    _check_scheduled_rows(payload.get("schedule_rows"), values)
    return set(values)


def completion(row, disposition, gaps):
    if row["status"] in ("failed", "skipped"):
        if row["task_count"]:
            corrupt()
        return "no_result"
    ids = scheduled_ids(row)
    if disposition is None or ids is None:
        gaps.append(gap("completeness"))
        return "unknown"
    expected = {item["op_id"] for item in disposition.values() if item["status"] != "skipped"}
    # Protected baseline rows outside the selected batches may legitimately be retained.
    missing = expected - ids
    raw_metrics = row["artifact"].get("metrics")
    if raw_metrics is not None and type(raw_metrics) is not dict:
        corrupt()
    metric_completion = (raw_metrics or {}).get("completion")
    incomplete = type(metric_completion) is dict and bool(metric_completion.get("incomplete_batch_ids"))
    return "partial" if missing or incomplete or any(item["status"] == "skipped" for item in disposition.values()) else "complete"


def metrics(artifact, gaps):
    raw = artifact.get("metrics")
    if raw is not None and type(raw) is not dict:
        corrupt()
    raw = raw or {}
    result = {}
    for key in _METRICS:
        issues = []
        undefined = key in ("machine_util_avg", "operator_util_avg") and raw.get("util_defined") is not True
        if undefined:
            value = None
            issues.append(gap("metrics." + key, "undefined_metric"))
        else:
            value = number(raw.get(key), "metrics." + key, issues, integer=key.endswith("_count"))
        result[key] = {"value": value, "reason": issues[0] if issues else None}
    result["elapsed_seconds"] = {"value": number(artifact.get("elapsed_seconds"), "elapsed_seconds", gaps), "reason": None}
    if result["elapsed_seconds"]["value"] is None:
        result["elapsed_seconds"]["reason"] = gaps[-1]
    return result


def candidate_summary(row, disposition):
    artifact, gaps = row["artifact"], []
    if artifact.get("status") != row["status"] or artifact.get("sequence") != row["sequence"]:
        corrupt()
    label = text(artifact.get("label"), "label", gaps)
    completeness = completion(row, disposition, gaps)
    status = "partial" if row["status"] == "completed" and completeness == "partial" else row["status"]
    reasons = blocked_reasons()
    if row["status"] != "completed":
        reasons.append({"capability": "preview", "code": "candidate_" + row["status"],
                        "message": "该候选未生成任务安排；可查看记录和导出空范围，未包装成完整方案。"})
    return {"candidate_ref": row["candidate_ref"], "run_ref": row["run_ref"], "label": label,
            "status": status, "persisted_status": row["status"], "task_count": row["task_count"],
            "completeness": completeness, "metrics": metrics(artifact, gaps),
            "metric_scopes": {"delivery": "completed_batches_only", "resources": "scheduled_results_only"},
            "capabilities": read_capabilities(), "blocked_reasons": reasons, "data_gaps": gaps}
