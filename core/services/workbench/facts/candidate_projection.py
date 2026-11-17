"""Public candidate summaries from persisted artifacts, without inferred costs.

Every artifact read here is either admitted once by ``CandidateStore`` (``candidate_artifact.admit_artifact``,
then bound to its candidate row) or built in this run from the same key table, so its keys are indexed directly
and its values are used as they are.
"""

from typing import Any, Dict

from core.models.workbench_run_candidate import blocked_reasons, read_capabilities, reference
from core.models.workbench_run_receipt import PersistedReceipt
from core.services.scheduler.config.config_field_spec import choice_label_map_for
from core.services.scheduler.run.schedule_candidate_plan import BUSINESS_FIELDS

from .candidate_artifact import SHOWN_METRICS_FIELDS
from .candidate_values import corrupt, gap, number

_SUMMARY_CANDIDATE_FIELDS = tuple(field for field in BUSINESS_FIELDS if field != "evaluations")


def business_candidate_fields(artifact, *, include_evaluations: bool = True):
    """Business facts every candidate of the unified search records."""
    fields = BUSINESS_FIELDS if include_evaluations else _SUMMARY_CANDIDATE_FIELDS
    return {field: artifact[field] for field in fields}


def dispositions(receipt, *, expected_refs):
    """A run's admitted operation dispositions, or None when it saved no candidate results.

    Queued/running runs have no receipt yet and failed/interrupted runs saved none; a persisted receipt records them.
    """
    if not isinstance(receipt, PersistedReceipt):
        return None
    return completed_dispositions(receipt.dispositions, expected_refs=expected_refs)


def completed_dispositions(value, *, expected_refs) -> Dict[str, Dict[str, Any]]:
    """Dispositions saved with a run's candidate results (or built at admission), indexed by operation.

    They cover exactly the run's admitted operations ``expected_refs``; any other scope is a corrupt archive.
    """
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


def validate_manifest(rows, receipt):
    """The run's candidate rows are exactly the ones its receipt lists; only a persisted receipt lists any, and it
    lists at least one (its state is the run's, ``CandidateStore.receipt``)."""
    if not isinstance(receipt, PersistedReceipt):
        if rows:
            corrupt()
        return
    expected = receipt.candidates
    if type(expected) is not list or len(expected) != len(rows) or not rows:
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
        if item is None or item.get("task_count") != row["task_count"]:
            corrupt()


def scheduled_ids(row):
    """Operations validated for the candidate's permanent task rows, the only arrangement record; the store
    admitted one per task row, each with its engine trace."""
    return set(row["artifact"]["validated_payload"]["scheduled_op_ids"])


def candidate_completeness(row, disposition, *, scheduled_op_ids):
    expected = {item["op_id"] for item in disposition.values() if item["status"] != "skipped"}
    # Protected baseline rows outside the selected batches may legitimately be retained.
    missing = expected - scheduled_op_ids
    incomplete = bool(row["artifact"]["metrics"]["completion"]["incomplete_batch_ids"])
    return "partial" if missing or incomplete or any(item["status"] == "skipped" for item in disposition.values()) else "complete"


def metrics(artifact):
    raw = artifact["metrics"]
    result = {}
    for key in SHOWN_METRICS_FIELDS:
        if key in ("machine_util_avg", "operator_util_avg") and not raw["util_defined"]:
            result[key] = {"value": None, "reason": gap("metrics." + key, "undefined_metric")}
        else:
            result[key] = {"value": raw[key], "reason": None}
    result["elapsed_seconds"] = {"value": None, "state": "not_applicable",
        "reason": {"field": "elapsed_seconds", "code": "shared_run_time", "message": "计算用时属于本轮共同优化。"}}
    return result


def candidate_summary(row, disposition, *, scheduled_op_ids):
    """The catalog card; ``status`` is derived from completeness, a saved candidate is always a completed one."""
    artifact = row["artifact"]
    business_fields = business_candidate_fields(artifact)
    completeness = candidate_completeness(row, disposition, scheduled_op_ids=scheduled_op_ids)
    status = "partial" if completeness == "partial" else "completed"
    reasons = blocked_reasons()
    return {"candidate_ref": row["candidate_ref"], "run_ref": row["run_ref"], "label": artifact["label"],
            "status": status, "task_count": row["task_count"],
            "completeness": completeness, "metrics": metrics(artifact),
            "metric_scopes": {"delivery": "completed_batches_only", "resources": "scheduled_results_only"},
            "capabilities": read_capabilities(), "blocked_reasons": reasons,
            **business_fields}


def algorithm_facts(artifact, *, business_fields):
    mode, strategy = artifact["algo_mode"], artifact["sort_strategy"]
    return {"mode": mode, "mode_label": choice_label_map_for("algo_mode")[mode],
            "strategy": strategy, "strategy_label": choice_label_map_for("sort_strategy")[strategy],
            **business_fields,
            "primary_objective": artifact["objective_name"], "target_objectives": artifact["target_objectives"]}


def baseline_capture(baseline, captured_at, *, kind="admission_official"):
    rows = baseline.get("rows")
    version = baseline.get("version")
    return {"baseline_ref": baseline.get("plan_ref"),
            "version": number(version, "baseline.version", [], integer=True) if version is not None else None,
            "kind": kind, "captured_at": captured_at,
            "captured_task_count": len(rows) if type(rows) is list else None}


def candidate_origin(candidate, run, capture):
    artifact = candidate["artifact"]
    return {"source_kind": "candidate_adoption", "source_ref": candidate["candidate_ref"],
            "source_label": artifact["label"],
            "run_ref": run["run_ref"], "accepted_at": run["accepted_at"], "finished_at": run["finished_at"],
            "algorithm": algorithm_facts(artifact, business_fields=business_candidate_fields(artifact, include_evaluations=False)),
            "baseline": baseline_capture(capture["baseline"], run["accepted_at"])}
