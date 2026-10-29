"""Public candidate summaries from persisted artifacts, without inferred costs."""

from typing import Any, Dict

from core.models.workbench_run_candidate import blocked_reasons, read_capabilities, reference
from core.services.scheduler.config.config_field_spec import choice_label_map_for
from core.shared.strict_json import clone_json

from .candidate_values import corrupt, gap, number, text

_METRICS = ("overdue_count", "total_tardiness_hours", "makespan_hours", "changeover_count",
            "weighted_tardiness_hours", "machine_used_count", "operator_used_count",
            "machine_busy_hours_total", "operator_busy_hours_total", "machine_util_avg", "operator_util_avg")
UNIFIED_GENERATION_VERSION = "unified_search_v1"


def business_candidate_fields(artifact):
    """Business facts every candidate of the unified search records; any other artifact is corrupt."""
    fields = ("generation_policy_version", "representative_objectives", "evaluations", "origin",
              "first_found_elapsed_ms", "search_evidence_ref")
    if any(field not in artifact for field in fields) or artifact["generation_policy_version"] != UNIFIED_GENERATION_VERSION:
        corrupt()
    return {field: artifact[field] for field in fields}


def dispositions(receipt, *, expected_refs):
    """A run's admitted operation dispositions, or None when it saved no candidate results.

    Queued/running runs have no receipt yet and failed/interrupted receipts save
    ``result_persisted: false``; every other receipt records them.
    """
    if receipt is None or receipt.get("result_persisted") is False:
        return None
    return completed_dispositions(receipt, expected_refs=expected_refs)


def completed_dispositions(receipt, *, expected_refs) -> Dict[str, Dict[str, Any]]:
    """Dispositions saved with a run's candidate results (or built at admission).

    They cover exactly the run's admitted operations ``expected_refs``; absence or
    any other scope is a corrupt archive.
    """
    value = receipt.get("dispositions")
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
    if set(result) != set(expected_refs):
        corrupt()
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
        if type(row) is not dict:
            corrupt()
        ref = reference(row.get("candidate_ref"), stored=True)
        if ref in index:
            corrupt()
        index[ref] = row
    for row in rows:
        item = index.get(row["candidate_ref"])
        if item is None or item.get("task_count") != row["task_count"] or item.get("status") != row["status"] or row["status"] != "completed":
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
    """Operations validated for the candidate's permanent task rows, the only arrangement record."""
    artifact = row["artifact"]
    payload = artifact.get("validated_payload")
    if artifact.get("task_payload_source") != "candidate_tasks_v1" or type(payload) is not dict:
        corrupt()
    values = _scheduled_values(payload, row)
    _check_scheduled_rows(artifact.get("results"), values)
    return set(values)


def completion(row, disposition, scheduled_op_ids):
    ids = scheduled_op_ids
    expected = {item["op_id"] for item in disposition.values() if item["status"] != "skipped"}
    # Protected baseline rows outside the selected batches may legitimately be retained.
    missing = expected - ids
    raw_metrics = row["artifact"].get("metrics")
    if raw_metrics is not None and type(raw_metrics) is not dict:
        corrupt()
    metric_completion = (raw_metrics or {}).get("completion")
    incomplete = type(metric_completion) is dict and bool(metric_completion.get("incomplete_batch_ids"))
    return "partial" if missing or incomplete or any(item["status"] == "skipped" for item in disposition.values()) else "complete"


def metrics(artifact):
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
    result["elapsed_seconds"] = {"value": None, "state": "not_applicable",
        "reason": {"field": "elapsed_seconds", "code": "shared_run_time", "message": "计算用时属于本轮共同优化。"}}
    return result


def candidate_summary(row, disposition, *, scheduled_op_ids):
    artifact, gaps = row["artifact"], []
    if row["status"] != "completed" or artifact.get("status") != row["status"] or artifact.get("sequence") != row["sequence"]:
        corrupt()
    label = text(artifact.get("label"), "label", gaps)
    completeness = completion(row, disposition, scheduled_op_ids)
    status = "partial" if completeness == "partial" else row["status"]
    reasons = blocked_reasons()
    return {"candidate_ref": row["candidate_ref"], "run_ref": row["run_ref"], "label": label,
            "status": status, "persisted_status": row["status"], "task_count": row["task_count"],
            "completeness": completeness, "metrics": metrics(artifact),
            "metric_scopes": {"delivery": "completed_batches_only", "resources": "scheduled_results_only"},
            "capabilities": read_capabilities(), "blocked_reasons": reasons, "data_gaps": gaps,
            **business_candidate_fields(artifact)}


def algorithm_facts(artifact):
    mode = text(artifact.get("algo_mode"), "algo_mode", [])
    strategy = text(artifact.get("used_strategy"), "used_strategy", [])
    return {"mode": mode, "mode_label": choice_label_map_for("algo_mode").get(mode) if mode is not None else None,
            "strategy": strategy, "strategy_label": choice_label_map_for("sort_strategy").get(strategy) if strategy is not None else None,
            **business_candidate_fields(artifact),
            "primary_objective": artifact["objective_name"], "target_objectives": list(artifact["target_objectives"])}


def algorithm_summary(artifact):
    fields = business_candidate_fields(artifact)
    summary_fields = {k: clone_json(v) for k, v in fields.items() if k != "evaluations"}
    mode = text(artifact.get("algo_mode"), "algo_mode", [])
    strategy = text(artifact.get("used_strategy"), "used_strategy", [])
    return {
        "mode": mode,
        "mode_label": choice_label_map_for("algo_mode").get(mode) if mode is not None else None,
        "strategy": strategy,
        "strategy_label": choice_label_map_for("sort_strategy").get(strategy) if strategy is not None else None,
        **summary_fields,
        "primary_objective": artifact["objective_name"],
        "target_objectives": list(artifact["target_objectives"]),
    }


def baseline_capture(baseline, captured_at, *, kind="admission_official"):
    rows = baseline.get("rows")
    version = baseline.get("version")
    return {"baseline_ref": baseline.get("plan_ref"),
            "version": number(version, "baseline.version", [], integer=True) if version is not None else None,
            "kind": kind, "captured_at": captured_at,
            "captured_task_count": len(rows) if type(rows) is list else None}


def candidate_origin(candidate, run, capture):
    return {"source_kind": "candidate_adoption", "source_ref": candidate["candidate_ref"],
            "source_label": text(candidate["artifact"].get("label"), "label", []),
            "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "algorithm": algorithm_summary(candidate["artifact"]),
            "baseline": baseline_capture(capture["baseline"], run["accepted_at"])}
