"""Fail-closed validation and diagnostic comparison for complete optimizer runs."""
from __future__ import annotations

from datetime import datetime

from core.algorithms.objective_specs import objective_metric_keys
from tests._support.optimizer_quality_matrix_compare import (
    MACHINE_KEYS,
    _integer,
    _text,
    _validate_source,
    exact_keys,
    finite_number,
)
from tests._support.optimizer_quality_matrix_provenance import proof_binding

CLAIM = "feasibility_and_restricted_tiny_oracle_not_general_optimality"
TOP_KEYS = {
    "schema_version", "kind", "claim", "config", "coverage", "measurement", "started_at", "finished_at",
    "machine", "source_before", "source_after", "proof_binding", "cases", "status",
}
ROW_KEYS = {
    "case_id", "scenario", "objective", "fixture_sha256", "scheduler_config", "operation_count", "constraint_tags",
    "runtime_ms", "decode_count", "optimizer_call_count", "first_improvement_ms", "selected_candidate_key",
    "candidates", "baseline", "selected", "oracle", "status", "errors",
}
CANDIDATE_KEYS = {
    "candidate_key", "status", "score", "runtime_ms", "decode_count", "optimizer_runtime_ms", "quality_vectors",
}


def _validate_run_metadata(snapshot):
    from tests._support.optimizer_end_to_end_cases import OBJECTIVES, SCENARIOS
    from tests._support.optimizer_end_to_end_runner import measurement_for_config, validate_config

    exact_keys(snapshot, TOP_KEYS, "snapshot")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1 or snapshot["kind"] != "optimizer_end_to_end_matrix":
        raise ValueError("unknown end-to-end schema")
    if snapshot["status"] != "passed":
        raise ValueError("snapshot status must be passed")
    validate_config(snapshot["config"])
    if snapshot["claim"] != CLAIM or snapshot["measurement"] != measurement_for_config(snapshot["config"]):
        raise ValueError("unknown measurement or proof claim")
    started, finished = (datetime.fromisoformat(snapshot[key]) for key in ("started_at", "finished_at"))
    if started.tzinfo is None or finished.tzinfo is None or started > finished:
        raise ValueError("invalid run timestamps")
    exact_keys(snapshot["coverage"], {"scenarios", "objectives"}, "coverage")
    for key, allowed in (("scenarios", SCENARIOS), ("objectives", OBJECTIVES)):
        selected = snapshot["coverage"][key]
        if not isinstance(selected, list) or not selected or any(type(value) is not str for value in selected):
            raise ValueError("invalid " + key + " coverage")
        if len(set(selected)) != len(selected) or not set(selected).issubset(allowed):
            raise ValueError("unknown or duplicate " + key + " coverage")
    exact_keys(snapshot["machine"], MACHINE_KEYS, "machine")
    for key, value in snapshot["machine"].items():
        if key == "cpu_count":
            _integer(value, key, 1)
        else:
            _text(value, key)
    before, after = snapshot["source_before"], snapshot["source_after"]
    _validate_source(before)
    _validate_source(after)
    for key in ("repo_root", "head", "source_sha256"):
        if before[key] != after[key]:
            raise ValueError("measured " + key + " changed during run; snapshot is diagnostic-only")
    if snapshot["proof_binding"] != proof_binding(before, after):
        raise ValueError("proof binding disagrees with git receipts")


def _validate_vectors(vectors):
    from tests._support.optimizer_end_to_end_cases import OBJECTIVES

    exact_keys(vectors, OBJECTIVES, "quality vectors")
    failed_counts = []
    for objective, vector in vectors.items():
        if not isinstance(vector, list) or len(vector) != 1 + len(objective_metric_keys(objective)):
            raise ValueError("objective score shape mismatch")
        for value in vector:
            finite_number(value, "objective score")
        if int(vector[0]) != vector[0]:
            raise ValueError("failed operation score must be an integer")
        failed_counts.append(vector[0])
    if len(set(failed_counts)) != 1:
        raise ValueError("quality vectors disagree on failed operations")


def _validate_payload(payload, data):
    from tests._support.optimizer_end_to_end_cases import audit_payload

    exact_keys(payload, {"failed_ops", "quality_vectors", "schedule"}, "schedule")
    _integer(payload["failed_ops"], "failed_ops")
    _validate_vectors(payload["quality_vectors"])
    if any(vector[0] != payload["failed_ops"] for vector in payload["quality_vectors"].values()):
        raise ValueError("failed operation accounting mismatch")
    if audit_payload(payload, data) != payload["quality_vectors"]:
        raise ValueError("quality vectors disagree with audited schedule")


def _validate_decode_count(value, config, label, minimum=0):
    if config["decoder_count_mode"] == "uncounted":
        if value is not None:
            raise ValueError(label + " must be null in uncounted mode")
    else:
        _integer(value, label, minimum)


def _validate_candidates(row, config):
    candidates = row["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a nonempty list")
    keys = []
    completed = {}
    for candidate in candidates:
        exact_keys(candidate, CANDIDATE_KEYS, "candidate")
        _text(candidate["candidate_key"], "candidate_key")
        keys.append(candidate["candidate_key"])
        if candidate["status"] not in {"completed", "skipped", "failed"}:
            raise ValueError("unknown candidate status")
        for key in ("runtime_ms", "optimizer_runtime_ms"):
            finite_number(candidate[key], key)
        if candidate["optimizer_runtime_ms"] > candidate["runtime_ms"] + 0.000001:
            raise ValueError("candidate optimizer/runtime accounting mismatch")
        _validate_decode_count(candidate["decode_count"], config, "candidate decode_count")
        if candidate["status"] == "completed":
            _validate_decode_count(candidate["decode_count"], config, "completed candidate decode_count", 1)
            _validate_vectors(candidate["quality_vectors"])
            if not isinstance(candidate["score"], list):
                raise ValueError("candidate score must be a list")
            for value in candidate["score"]:
                finite_number(value, "candidate score")
            if candidate["score"] != candidate["quality_vectors"][row["objective"]]:
                raise ValueError("candidate score disagrees with quality vector")
            completed[candidate["candidate_key"]] = candidate
        elif candidate["score"] is not None or candidate["quality_vectors"] is not None:
            raise ValueError("incomplete candidate cannot claim scored quality")
        if candidate["status"] != "completed":
            if (config["decoder_count_mode"] == "native" and candidate["decode_count"] != 0) or candidate["optimizer_runtime_ms"] != 0:
                raise ValueError("unexecuted candidate cannot claim optimizer work")
    if len(keys) != len(set(keys)) or not completed:
        raise ValueError("duplicate candidates or no completed candidate")
    count = config["weight_count"]
    expected_keys = ["baseline"] + ["graph_w" + str(index) + "_of_" + str(count) for index in range(1, count + 1)]
    if keys != expected_keys:
        raise ValueError("missing, unknown or reordered candidate keys")
    if row["optimizer_call_count"] != len(completed):
        raise ValueError("optimizer call accounting mismatch")
    for role, candidate_key in (("baseline", "baseline"), ("selected", row["selected_candidate_key"])):
        if candidate_key not in completed or completed[candidate_key]["quality_vectors"] != row[role]["quality_vectors"]:
            raise ValueError(role + " payload disagrees with completed candidate")
    if tuple(completed[row["selected_candidate_key"]]["score"]) != min(tuple(candidate["score"]) for candidate in completed.values()):
        raise ValueError("score_only selection did not choose the best completed score")
    if config["decoder_count_mode"] == "native" and sum(candidate["decode_count"] for candidate in candidates) != row["decode_count"]:
        raise ValueError("decode accounting mismatch")
    if sum(candidate["runtime_ms"] for candidate in candidates) > row["runtime_ms"] + 0.000001:
        raise ValueError("candidate/total runtime accounting mismatch")


def _validate_oracle(report):
    from tests._support.optimizer_end_to_end_cases import OBJECTIVES

    exact_keys(report, {"applicable", "reason", "optimum_vectors", "selected_vectors", "lexicographic_gaps"}, "oracle")
    if type(report["applicable"]) is not bool:
        raise ValueError("oracle applicable must be a bool")
    _text(report["reason"], "oracle reason")
    if not report["applicable"]:
        if any(report[key] is not None for key in ("optimum_vectors", "selected_vectors", "lexicographic_gaps")):
            raise ValueError("inapplicable oracle cannot claim optimality")
        return
    for key in ("optimum_vectors", "selected_vectors"):
        _validate_vectors(report[key])
    exact_keys(report["lexicographic_gaps"], OBJECTIVES, "oracle gaps")
    for objective, gap in report["lexicographic_gaps"].items():
        exact_keys(gap, {"first_differing_index", "delta", "optimal"}, "oracle gap")
        finite_number(gap["delta"], "oracle delta")
        if type(gap["optimal"]) is not bool:
            raise ValueError("oracle optimal must be a bool")
        if gap["first_differing_index"] is not None:
            _integer(gap["first_differing_index"], "oracle first_differing_index")
            if gap["first_differing_index"] >= len(report["selected_vectors"][objective]):
                raise ValueError("oracle gap index outside score vector")


def _validate_row(row, config):
    from tests._support.optimizer_end_to_end_cases import fixture_data, scheduler_config
    from tests._support.optimizer_end_to_end_runner import oracle_report
    from tests._support.optimizer_quality_matrix_cases import json_hash

    exact_keys(row, ROW_KEYS, "case")
    if row["case_id"] != row["scenario"] + "/" + row["objective"]:
        raise ValueError("case identity mismatch")
    data = fixture_data(row["scenario"])
    if row["fixture_sha256"] != json_hash(data):
        raise ValueError("fixture mismatch")
    if json_hash(row["scheduler_config"]) != json_hash(scheduler_config(row["scenario"], row["objective"], config)):
        raise ValueError("scheduler config mismatch")
    if row["constraint_tags"] != data["constraint_tags"]:
        raise ValueError("constraint tags mismatch")
    _integer(row["operation_count"], "operation_count", 1)
    if row["operation_count"] != len(data["operations"]):
        raise ValueError("operation count mismatch")
    if row["status"] != "passed" or row["errors"] != []:
        raise ValueError("case status must be passed")
    finite_number(row["runtime_ms"], "runtime_ms", 0.000000001)
    _validate_decode_count(row["decode_count"], config, "decode_count", 1)
    _integer(row["optimizer_call_count"], "optimizer_call_count", 1)
    if row["first_improvement_ms"] is not None:
        finite_number(row["first_improvement_ms"], "first_improvement_ms")
        if row["first_improvement_ms"] > row["runtime_ms"]:
            raise ValueError("first improvement exceeds run duration")
    _text(row["selected_candidate_key"], "selected_candidate_key")
    for role in ("baseline", "selected"):
        _validate_payload(row[role], data)
    _validate_candidates(row, config)
    if tuple(row["selected"]["quality_vectors"][row["objective"]]) > tuple(row["baseline"]["quality_vectors"][row["objective"]]):
        raise ValueError("selected quality regressed against same-run baseline")
    _validate_oracle(row["oracle"])
    if row["oracle"] != oracle_report(data, row["selected"]):
        raise ValueError("restricted tiny oracle report mismatch")


def validate_snapshot(snapshot):
    _validate_run_metadata(snapshot)
    rows = snapshot["cases"]
    if not isinstance(rows, list):
        raise ValueError("cases must be a list")
    expected = {scenario + "/" + objective for scenario in snapshot["coverage"]["scenarios"]
                for objective in snapshot["coverage"]["objectives"]}
    for row in rows:
        exact_keys(row, ROW_KEYS, "case")
        _text(row["case_id"], "case_id")
    if len(rows) != len(expected) or {row["case_id"] for row in rows} != expected:
        raise ValueError("missing, extra or duplicate case")
    for row in rows:
        _validate_row(row, snapshot["config"])


def compare_end_to_end_matrices(baseline, actual, runtime_ratio=3.0, runtime_slack_ms=250.0):
    finite_number(runtime_ratio, "runtime_ratio", 1.0)
    finite_number(runtime_slack_ms, "runtime_slack_ms")
    failures = []
    quality_changes = []
    for label, snapshot in (("baseline", baseline), ("actual", actual)):
        try:
            validate_snapshot(snapshot)
        except (ValueError, TypeError, KeyError, OverflowError) as exc:
            failures.append(label + ": " + str(exc))
    if not failures:
        for key in ("config", "coverage", "machine", "measurement"):
            if baseline[key] != actual[key]:
                failures.append(key + " mismatch; comparison requires same fixtures, environment and budget")
    if not failures:
        before_rows = {row["case_id"]: row for row in baseline["cases"]}
        for row in actual["cases"]:
            before = before_rows[row["case_id"]]
            for role in ("baseline", "selected"):
                for objective, vector in row[role]["quality_vectors"].items():
                    previous = before[role]["quality_vectors"][objective]
                    if vector != previous:
                        quality_changes.append({
                            "case_id": row["case_id"], "role": role, "objective": objective,
                            "before": previous, "after": vector, "governing_objective": objective == row["objective"],
                        })
                    if objective == row["objective"] and tuple(vector) > tuple(previous):
                        failures.append(row["case_id"] + ": " + role + " " + objective + " quality regressed")
            if row["runtime_ms"] > before["runtime_ms"] * runtime_ratio + runtime_slack_ms:
                failures.append(row["case_id"] + ": runtime_ms regressed")
    return {
        "status": "failed" if failures else "passed", "failures": failures,
        "quality_changes": quality_changes,
        "runtime_ratio": runtime_ratio, "runtime_slack_ms": runtime_slack_ms,
        "claim": "diagnostic_comparison_not_clean_quality_gate_proof",
        "runtime_interpretation": "single_run_large_regression_guard_not_speedup_evidence",
    }
