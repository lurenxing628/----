"""Fail-closed matrix reader/comparator; independent from the old ratchet."""
from __future__ import annotations

import math
import re
from datetime import datetime

from core.algorithms.objective_specs import objective_metric_keys
from tests._support.optimizer_quality_matrix import validate_run_config
from tests._support.optimizer_quality_matrix_cases import (
    OBJECTIVES,
    SCENARIOS,
    case_environment,
    json_hash,
    scheduler_config,
)
from tests._support.optimizer_quality_matrix_provenance import proof_binding
from tests._support.optimizer_quality_matrix_schedule import audit_schedule

TOP_KEYS = {"schema_version", "kind", "started_at", "finished_at", "status", "claim", "config", "measurement",
            "machine", "source_before", "source_after", "proof_binding", "cases"}
ROW_KEYS = {"case_id", "scenario", "objective", "seed", "operation_count", "fixture_sha256", "scheduler_config",
            "baseline", "improved", "baseline_runtime_ms", "improve_runtime_ms", "runtime_ms", "counts", "repair", "status", "errors"}
SOURCE_KEYS = {"repo_root", "head", "branch", "status_porcelain", "worktree_clean", "diff_sha256", "source_sha256"}
MACHINE_KEYS = {"node", "platform", "machine", "cpu_count", "python_version", "python_implementation", "python_executable",
                "sqlite_version", "networkx_version"}
MEASUREMENT = {"clock": "time.perf_counter", "execution": "serial_single_worker",
               "scope": "baseline_sgs_plus_graph_ready_production_repair_excludes_fixture_and_audit"}


def exact_keys(value, keys, label):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError("unknown or missing " + label + " metadata")


def finite_number(value, label, minimum=0):
    if type(value) not in (int, float) or not math.isfinite(value) or value < minimum:
        raise ValueError("invalid " + label)


def _integer(value, label, minimum=0):
    if type(value) is not int or value < minimum:
        raise ValueError("invalid " + label)


def _text(value, label):
    if not isinstance(value, str) or not value.strip() or value.strip().lower() in {"unknown", "none", "null", "unavailable"}:
        raise ValueError("unknown " + label)


def _validate_source(source):
    exact_keys(source, SOURCE_KEYS, "source")
    for key in ("repo_root", "branch"):
        _text(source[key], key)
    for key, size in (("head", 40), ("diff_sha256", 64), ("source_sha256", 64)):
        if not isinstance(source[key], str) or re.fullmatch("[0-9a-f]{" + str(size) + "}", source[key]) is None:
            raise ValueError("unknown " + key)
    status = source["status_porcelain"]
    if not isinstance(status, list) or any(not isinstance(item, str) or not item for item in status):
        raise ValueError("unknown git status")
    if type(source["worktree_clean"]) is not bool or source["worktree_clean"] != (not status):
        raise ValueError("worktree clean/status mismatch")


def validate_snapshot(snapshot):
    exact_keys(snapshot, TOP_KEYS, "snapshot")
    if type(snapshot["schema_version"]) is not int or snapshot["schema_version"] != 1 or snapshot["kind"] != "optimizer_quality_matrix":
        raise ValueError("unknown matrix schema")
    if snapshot["status"] != "passed":
        raise ValueError("snapshot status must be passed")
    if snapshot["claim"] != "feasibility_and_non_regression_only_not_optimality" or snapshot["measurement"] != MEASUREMENT:
        raise ValueError("unknown measurement or proof claim")
    started, finished = (datetime.fromisoformat(snapshot[key]) for key in ("started_at", "finished_at"))
    if started.tzinfo is None or finished.tzinfo is None or started > finished:
        raise ValueError("invalid run timestamps")
    config = snapshot["config"]
    validate_run_config(config)
    exact_keys(snapshot["machine"], MACHINE_KEYS, "machine")
    for key, value in snapshot["machine"].items():
        if key == "cpu_count":
            _integer(value, key, 1)
        else:
            _text(value, key)
    for key in ("source_before", "source_after"):
        _validate_source(snapshot[key])
    # Unrelated status/diff drift is diagnostic; mixed measurement sources are not comparable.
    for key in ("source_sha256", "head"):
        if snapshot["source_before"][key] != snapshot["source_after"][key]:
            raise ValueError("measured " + key + " changed during run; snapshot is diagnostic-only")
    if snapshot["proof_binding"] != proof_binding(snapshot["source_before"], snapshot["source_after"]):
        raise ValueError("proof binding disagrees with git receipts")
    rows = snapshot["cases"]
    if not isinstance(rows, list):
        raise ValueError("cases must be a list")
    expected = {scenario + "/" + objective for scenario in SCENARIOS for objective in OBJECTIVES}
    for row in rows:
        exact_keys(row, ROW_KEYS, "case")
    if len(rows) != len(expected) or {row["case_id"] for row in rows} != expected:
        raise ValueError("missing, extra or duplicate case")
    for scenario in SCENARIOS:
        with case_environment(scenario) as env:
            for row in rows:
                if row["case_id"].split("/")[0] == scenario:
                    _validate_row(row, config, env)


def _validate_row(row, config, env):
    scenario, objective = row["case_id"].split("/")
    if row["scenario"] != scenario or row["objective"] != objective:
        raise ValueError("case identity mismatch")
    _integer(row["seed"], "seed")
    if row["seed"] != config["seed"]:
        raise ValueError("case seed mismatch")
    if type(row["operation_count"]) is not int or row["operation_count"] != len(env["operations"]) or row["fixture_sha256"] != json_hash(env["data"]):
        raise ValueError("fixture mismatch")
    expected_config = scheduler_config(scenario, objective, config["time_budget_seconds"])
    if json_hash(row["scheduler_config"]) != json_hash(expected_config):
        raise ValueError("scheduler config mismatch")
    if row["status"] != "passed" or row["errors"] != []:
        raise ValueError("case status must be passed")
    for key in ("baseline_runtime_ms", "improve_runtime_ms", "runtime_ms"):
        finite_number(row[key], key, 0.000000001)
    if not math.isclose(row["runtime_ms"], row["baseline_runtime_ms"] + row["improve_runtime_ms"], rel_tol=1e-12):
        raise ValueError("runtime accounting mismatch")
    counts = row["counts"]
    exact_keys(counts, {"baseline_decode_count", "graph_decode_count", "repair_decode_count"}, "decode counts")
    for key, value in counts.items():
        _integer(value, key, 1)
    if counts["baseline_decode_count"] != 1 or counts["graph_decode_count"] + counts["repair_decode_count"] > config["max_candidates"]:
        raise ValueError("decode budget mismatch")
    repair = row["repair"]
    exact_keys(repair, {"repair_scope", "repair_status", "repair_evaluated_candidates"}, "repair")
    if repair["repair_scope"] != "production_core" or repair["repair_status"] not in {
            "strict_improvement", "no_strict_improvement", "all_candidates_rejected"}:
        raise ValueError("production repair not exercised")
    _integer(repair["repair_evaluated_candidates"], "repair_evaluated_candidates", 1)
    if repair["repair_evaluated_candidates"] != counts["repair_decode_count"]:
        raise ValueError("repair decode count mismatch")
    for key in ("baseline", "improved"):
        _validate_score(row[key], objective)
        audit_schedule(row[key], env, objective)
    if row["improved"]["failed_ops"] > row["baseline"]["failed_ops"] or tuple(row["improved"]["objective_score"]) > tuple(row["baseline"]["objective_score"]):
        raise ValueError("quality regressed against same-environment baseline")


def _validate_score(payload, objective):
    exact_keys(payload, {"objective_score", "failed_ops", "schedule"}, "schedule")
    score = payload["objective_score"]
    if not isinstance(score, list) or len(score) != 1 + len(objective_metric_keys(objective)):
        raise ValueError("objective score shape mismatch")
    for value in score:
        finite_number(value, "objective score")


def _snapshot_comparison_failures(baseline, actual):
    failures = []
    for label, snapshot in (("baseline", baseline), ("actual", actual)):
        try:
            validate_snapshot(snapshot)
        except (ValueError, TypeError, KeyError) as exc:
            failures.append(label + ": " + str(exc))
    return failures


def _quality_comparison_failures(baseline, actual):
    failures = []
    for key in ("config", "measurement"):
        if baseline[key] != actual[key]:
            failures.append(key + " mismatch; quality comparison requires the same fixture and budget")
    base_rows = {row["case_id"]: row for row in baseline["cases"]}
    for row in actual["cases"]:
        before = base_rows[row["case_id"]]
        for role in ("baseline", "improved"):
            if tuple(row[role]["objective_score"]) > tuple(before[role]["objective_score"]):
                failures.append(row["case_id"] + ": " + role + " objective regressed")
    return failures


def compare_quality_only(baseline, actual):
    """Compare validated historical quality across hosts; never claim runtime proof."""
    failures = _snapshot_comparison_failures(baseline, actual)
    if not failures:
        failures.extend(_quality_comparison_failures(baseline, actual))
    return {"status": "failed" if failures else "passed", "failures": failures,
            "claim": "quality_only_not_runtime_or_clean_quality_gate_proof"}


def compare_quality_matrices(baseline, actual, runtime_ratio=3.0, runtime_slack_ms=250.0):
    finite_number(runtime_ratio, "runtime_ratio", 1.0)
    finite_number(runtime_slack_ms, "runtime_slack_ms")
    failures = _snapshot_comparison_failures(baseline, actual)
    if not failures:
        failures.extend(_quality_comparison_failures(baseline, actual))
        if baseline["machine"] != actual["machine"]:
            failures.append("machine mismatch; runtime comparison requires same environment and budget")
        base_rows = {row["case_id"]: row for row in baseline["cases"]}
        for row in actual["cases"]:
            before = base_rows[row["case_id"]]
            for key in ("baseline_runtime_ms", "improve_runtime_ms", "runtime_ms"):
                if row[key] > before[key] * runtime_ratio + runtime_slack_ms:
                    failures.append(row["case_id"] + ": " + key + " regressed")
    return {"status": "failed" if failures else "passed", "failures": failures,
            "runtime_ratio": runtime_ratio, "runtime_slack_ms": runtime_slack_ms,
            "claim": "diagnostic_comparison_not_clean_quality_gate_proof"}
