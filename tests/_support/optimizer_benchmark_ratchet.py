from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.services.scheduler.run.optimizer_graph_ready_profiles import graph_ready_weight_profile_summary
from core.services.scheduler.run.optimizer_proof_harness import run_optimizer_proof_harness
from tests._support.optimizer_graph_ready_benchmark import (
    GRAPH_READY_FLEXIBLE_MACHINE_CASE_GROUP,
    GRAPH_READY_FLEXIBLE_MACHINE_CASE_SLUG,
    GRAPH_READY_REAL_SGS_CASE_GROUP,
    GRAPH_READY_REAL_SGS_CASE_SLUG,
    run_graph_ready_flexible_machine_metric_case,
    run_graph_ready_real_sgs_case,
)

RATCHET_SCHEMA_VERSION = 1
DEFAULT_BASELINE = Path(".codestable/roadmap/scheduler-global-optimizer/benchmark-ratchet-baseline.json")


def build_light_ratchet_snapshot(*, repo_root: Path) -> Dict[str, Any]:
    proof = run_optimizer_proof_harness(require_optimal=True)["public"]
    rows = [_proof_case_row(case) for case in proof.get("cases") or []]
    rows.append(run_graph_ready_real_sgs_case(seed=0))
    rows.append(run_graph_ready_flexible_machine_metric_case())
    return {
        "schema_version": RATCHET_SCHEMA_VERSION,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_commit": _git_commit(repo_root),
        "dirty_worktree": _dirty_worktree(repo_root),
        "tier": "light",
        "status": "passed" if proof.get("status") == "passed" and _rows_pass(rows) else "failed",
        "case_count": len(rows),
        "cases": rows,
        "graph_ready_optimization": graph_ready_weight_profile_summary(),
    }


def compare_to_baseline(actual: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    actual_cases = [row for row in actual.get("cases") or [] if isinstance(row, dict)]
    baseline_cases = [row for row in baseline.get("cases") or [] if isinstance(row, dict)]
    actual_rows = {_case_key(row): row for row in actual_cases}
    baseline_rows = {_case_key(row): row for row in baseline_cases}
    failures = _worktree_proof_failures(actual, baseline)
    failures.extend(_case_collection_failures(actual, actual_cases, baseline, baseline_cases))
    failures.extend(_missing_case_failures(actual_rows, baseline_rows))
    failures.extend(_matching_row_failures(actual_cases, baseline_rows))
    status = "passed" if not failures and actual.get("status") == "passed" else "failed"
    return {
        "schema_version": RATCHET_SCHEMA_VERSION,
        "status": status,
        "failure_count": len(failures),
        "failures": failures,
        "proof_binding_status": _proof_binding_status(actual, baseline),
    }


def load_baseline(path: Path) -> Optional[Dict[str, Any]]:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def write_baseline(path: Path, snapshot: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _proof_case_row(case: Dict[str, Any]) -> Dict[str, Any]:
    counts = case.get("aggregate_counts") if isinstance(case.get("aggregate_counts"), dict) else {}
    gap_to_oracle = _valid_float(case.get("gap_to_oracle_pct"))
    gap_comparison = _gap_comparison(gap_to_oracle)
    return {
        "schema_version": RATCHET_SCHEMA_VERSION,
        "case_group": "tiny",
        "case_slug": str(case.get("case_slug") or ""),
        "algorithm_profile": "graph_ready",
        "candidate_origin": "graph_ready_weight_grid",
        "seed": 0,
        "time_budget_seconds": 0,
        "objective_name": str(case.get("objective_name") or "min_overdue"),
        "objective_score": [],
        "oracle_status": str(case.get("oracle_status") or ""),
        "gap_to_oracle_pct": gap_to_oracle,
        "objective_score_matched": bool(case.get("objective_score_matched")),
        "failed_ops": int(counts.get("failed_ops") or 0),
        "runtime_ms": 0,
        "distinct_candidates": 0,
        "same_fingerprint_rejections": 0,
        "candidate_rejections": {},
        "reference_type": str(case.get("reference_type") or ""),
        "comparison_to_meta_baseline": {
            "metric": "gap_to_oracle_pct",
            "baseline_value": 0.0,
            "actual_value": gap_to_oracle,
            "delta_abs": gap_to_oracle,
            "delta_pct": 0.0,
            "status": gap_comparison,
        },
    }


def _row_failures(row: Dict[str, Any], base: Dict[str, Any]) -> List[Dict[str, Any]]:
    if _case_key(row) == (GRAPH_READY_REAL_SGS_CASE_GROUP, GRAPH_READY_REAL_SGS_CASE_SLUG):
        return _graph_ready_row_failures(row, base)
    if _case_key(row) == (GRAPH_READY_FLEXIBLE_MACHINE_CASE_GROUP, GRAPH_READY_FLEXIBLE_MACHINE_CASE_SLUG):
        return _graph_ready_metric_row_failures(row, base)
    failures: List[Dict[str, Any]] = []
    for metric, tolerance in (("gap_to_oracle_pct", 0.0), ("failed_ops", 0.0)):
        failure = _float_metric_increase_failure(_case_key(row), row, base, metric, tolerance=tolerance)
        if failure is not None:
            failures.append(failure)
    if not bool(row.get("objective_score_matched")):
        failures.append({"case": _case_key(row), "metric": "objective_score_matched", "actual": False})
    return failures


def _case_collection_failures(
    actual: Dict[str, Any],
    actual_cases: List[Dict[str, Any]],
    baseline: Dict[str, Any],
    baseline_cases: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    if not actual_cases:
        failures.append({"reason": "empty_actual_cases"})
    if not baseline_cases:
        failures.append({"reason": "empty_baseline_cases"})
    failures.extend(_case_count_failures("actual", actual, actual_cases))
    failures.extend(_case_count_failures("baseline", baseline, baseline_cases))
    return failures


def _proof_binding_status(actual: Dict[str, Any], baseline: Dict[str, Any]) -> str:
    if actual.get("dirty_worktree") is True or baseline.get("dirty_worktree") is True:
        return "unbound_dirty_worktree"
    if actual.get("dirty_worktree") is False and baseline.get("dirty_worktree") is False:
        return "clean_worktree"
    return "unknown_worktree_state"


def _worktree_proof_failures(actual: Dict[str, Any], baseline: Dict[str, Any]) -> List[Dict[str, str]]:
    failures: List[Dict[str, str]] = []
    if actual.get("dirty_worktree") is True:
        failures.append({"reason": "dirty_actual_worktree"})
    if baseline.get("dirty_worktree") is True:
        failures.append({"reason": "dirty_baseline_worktree"})
    return failures


def _case_count_failures(label: str, snapshot: Dict[str, Any], cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected = int(snapshot.get("case_count") or 0)
    if expected == len(cases):
        return []
    return [
        {
            "reason": f"{label}_case_count_mismatch",
            "case_count": expected,
            f"{label}_len": len(cases),
        }
    ]


def _missing_case_failures(
    actual_rows: Dict[Tuple[str, str], Dict[str, Any]],
    baseline_rows: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    failures = [{"case": key, "reason": "missing_actual_case"} for key in sorted(set(baseline_rows) - set(actual_rows))]
    failures.extend({"case": key, "reason": "missing_baseline"} for key in sorted(set(actual_rows) - set(baseline_rows)))
    return failures


def _matching_row_failures(
    actual_cases: List[Dict[str, Any]],
    baseline_rows: Dict[Tuple[str, str], Dict[str, Any]],
) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for row in actual_cases:
        base = baseline_rows.get(_case_key(row))
        if base is not None:
            failures.extend(_row_failures(row, base))
    return failures


def _graph_ready_row_failures(row: Dict[str, Any], base: Dict[str, Any]) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    case = _case_key(row)
    failures.extend(_graph_ready_count_failures(case, row, base))
    baseline_score = _score_tuple(base.get("objective_score"))
    actual_score = _score_tuple(row.get("objective_score"))
    if not actual_score:
        failures.append({"case": case, "metric": "objective_score", "actual": row.get("objective_score")})
    elif baseline_score and actual_score > baseline_score:
        failures.append({"case": case, "metric": "objective_score", "baseline": list(baseline_score), "actual": list(actual_score)})
    if not bool(row.get("objective_score_matched")):
        failures.append({"case": case, "metric": "objective_score_matched", "actual": False})
    if str(row.get("best_origin") or "") == "baseline":
        failures.append({"case": case, "metric": "best_origin", "actual": "baseline"})
    if str(row.get("status") or "") != "passed":
        failures.append({"case": case, "metric": "status", "actual": str(row.get("status") or "")})
    return failures


def _graph_ready_count_failures(case: Tuple[str, str], row: Dict[str, Any], base: Dict[str, Any]) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    failure = _float_metric_increase_failure(case, row, base, "failed_ops")
    if failure is not None:
        failures.append(failure)
    for metric in ("candidate_profile_count", "evaluated_candidates", "distinct_candidates", "accepted_distinct_candidates"):
        failure = _int_metric_decrease_failure(case, row, base, metric)
        if failure is not None:
            failures.append(failure)
    failure = _int_metric_increase_failure(case, row, base, "same_fingerprint_rejections")
    if failure is not None:
        failures.append(failure)
    return failures


def _graph_ready_metric_row_failures(row: Dict[str, Any], base: Dict[str, Any]) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    case = _case_key(row)
    if int(row.get("failed_ops") or 0) != 0:
        failures.append({"case": case, "metric": "failed_ops", "actual": int(row.get("failed_ops") or 0)})
    if not bool(row.get("objective_score_matched")):
        failures.append({"case": case, "metric": "objective_score_matched", "actual": False})
    if str(row.get("status") or "") != "passed":
        failures.append({"case": case, "metric": "status", "actual": str(row.get("status") or "")})

    scores = _score_map(row.get("bottleneck_scores"))
    baseline_scores = _score_map(base.get("bottleneck_scores"))
    failures.extend(_bottleneck_score_failures(case, scores, baseline_scores))
    if not _bottleneck_score_order_ok(scores):
        failures.append({"case": case, "metric": "bottleneck_score_order", "actual": scores})
    return failures


def _bottleneck_score_failures(
    case: Tuple[str, str],
    scores: Dict[str, float],
    baseline_scores: Dict[str, float],
) -> List[Dict[str, Any]]:
    failures: List[Dict[str, Any]] = []
    for name in ("busy", "light", "flex"):
        if name not in scores:
            failures.append({"case": case, "metric": f"bottleneck_scores.{name}", "actual": "missing"})
            continue
        if name not in baseline_scores:
            failures.append({"case": case, "metric": f"baseline_bottleneck_scores.{name}", "actual": "missing"})
            continue
        if abs(scores[name] - baseline_scores[name]) > 0.000001:
            failures.append(
                {
                    "case": case,
                    "metric": f"bottleneck_scores.{name}",
                    "baseline": baseline_scores[name],
                    "actual": scores[name],
                }
            )
    return failures


def _bottleneck_score_order_ok(scores: Dict[str, float]) -> bool:
    return scores.get("flex", 0.0) < scores.get("light", 0.0) < scores.get("busy", 0.0)


def _float_metric_increase_failure(
    case: Tuple[str, str],
    row: Dict[str, Any],
    base: Dict[str, Any],
    metric: str,
    *,
    tolerance: float = 0.0,
) -> Optional[Dict[str, Any]]:
    actual = _valid_float(row.get(metric))
    baseline = _valid_float(base.get(metric))
    if actual is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_actual_{metric}"}
    if baseline is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_baseline_{metric}"}
    if actual <= baseline + tolerance:
        return None
    return {"case": case, "metric": metric, "baseline": baseline, "actual": actual}


def _valid_float(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _gap_comparison(gap_to_oracle: Optional[float]) -> str:
    if gap_to_oracle is None:
        return "not_comparable"
    return "same" if gap_to_oracle == 0.0 else "degraded"


def _valid_int_metric(value: Any) -> Optional[int]:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _int_metric_increase_failure(
    case: Tuple[str, str],
    row: Dict[str, Any],
    base: Dict[str, Any],
    metric: str,
) -> Optional[Dict[str, Any]]:
    actual = _valid_int_metric(row.get(metric))
    baseline = _valid_int_metric(base.get(metric))
    if actual is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_actual_{metric}"}
    if baseline is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_baseline_{metric}"}
    if actual <= baseline:
        return None
    return {"case": case, "metric": metric, "baseline": baseline, "actual": actual}


def _int_metric_decrease_failure(
    case: Tuple[str, str],
    row: Dict[str, Any],
    base: Dict[str, Any],
    metric: str,
) -> Optional[Dict[str, Any]]:
    actual = _valid_int_metric(row.get(metric))
    baseline = _valid_int_metric(base.get(metric))
    if actual is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_actual_{metric}"}
    if baseline is None:
        return {"case": case, "metric": metric, "reason": f"missing_or_invalid_baseline_{metric}"}
    if actual >= baseline:
        return None
    return {"case": case, "metric": metric, "baseline": baseline, "actual": actual}


def _case_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return str(row.get("case_group") or ""), str(row.get("case_slug") or "")


def _rows_pass(rows: List[Dict[str, Any]]) -> bool:
    if not rows:
        return False
    for row in rows:
        if int(row.get("failed_ops") or 0) != 0 or not bool(row.get("objective_score_matched")):
            return False
        if _case_key(row) == (GRAPH_READY_REAL_SGS_CASE_GROUP, GRAPH_READY_REAL_SGS_CASE_SLUG):
            if str(row.get("status") or "") != "passed":
                return False
        if _case_key(row) == (GRAPH_READY_FLEXIBLE_MACHINE_CASE_GROUP, GRAPH_READY_FLEXIBLE_MACHINE_CASE_SLUG):
            if str(row.get("status") or "") != "passed":
                return False
    return True


def _score_tuple(value: Any) -> Tuple[float, ...]:
    if not isinstance(value, (list, tuple)):
        return ()
    return tuple(float(item) for item in value)


def _score_map(value: Any) -> Dict[str, float]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
    }


def _git_commit(repo_root: Path) -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True)
    except Exception:
        return "unknown"
    return out.strip()


def _dirty_worktree(repo_root: Path) -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--short"], cwd=str(repo_root), text=True)
    except Exception:
        return True
    return bool(out.strip())
