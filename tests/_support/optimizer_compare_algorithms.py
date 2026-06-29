"""Small, same-objective optimizer comparison matrix for GraphReady work."""

from __future__ import annotations

import math
import random
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core.algorithms import SortStrategy
from core.algorithms.greedy.algo_stats import snapshot_algo_stats
from core.services.scheduler.run.optimizer_candidate_fingerprint import build_candidate_fingerprint
from core.services.scheduler.run.optimizer_candidate_profile import derive_grasp_ig_limits
from core.services.scheduler.run.optimizer_grasp_ig_candidates import run_grasp_ig_candidates
from core.services.scheduler.run.optimizer_local_search import run_local_search
from core.services.scheduler.run.optimizer_search_report import OptimizationSearchReportState
from tests._support.optimizer_compare_algorithms_report import (
    compare_to_algorithm_baseline,
    summarize_comparison_rows,
)
from tests._support.optimizer_graph_ready_benchmark import (
    BASE_BATCH_ORDER,
    OBJECTIVE_NAME,
    START_DT,
    BenchmarkClock,
    _baseline_candidate,
    _result_order,
    _schedule_with_scheduler,
    _scheduler,
    _score_list,
    graph_ready_benchmark_batches,
    graph_ready_benchmark_operations,
    run_graph_ready_real_sgs_case,
)
from tests._support.optimizer_graph_ready_v2_benchmark import run_graph_ready_v2_real_sgs_case
from tests._support.optimizer_reference_diagnostics import build_reference_diagnostics

COMPARE_SCHEMA_VERSION = 1
COMPARE_CASE_GROUP = "graph_ready"
COMPARE_CASE_SLUG = "graph-ready-weight-grid-real-sgs"
DEFAULT_ALGORITHM_PROFILES = (
    "greedy",
    "local_search",
    "grasp_ig",
    "graph_ready_v1",
    "graph_ready_v2_no_repair",
    "graph_ready_v2_with_repair",
    "portfolio_all",
)


def build_algorithm_comparison(*, profiles: Sequence[str], seeds: int) -> Dict[str, Any]:
    normalized_profiles = _normalize_profiles(profiles)
    all_rows: List[Dict[str, Any]] = []
    for seed in range(int(seeds)):
        seed_rows = _run_seed_profiles(seed=seed, profiles=normalized_profiles)
        _attach_comparisons(seed_rows)
        all_rows.extend(seed_rows)
    dirty_worktree = _dirty_worktree(Path.cwd())
    payload = {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "status": "passed" if all_rows and all(row.get("status") == "passed" for row in all_rows) else "failed",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_commit": _git_commit(Path.cwd()),
        "dirty_worktree": dirty_worktree,
        "proof_binding_status": "unbound_dirty_worktree" if dirty_worktree else "clean_worktree",
        "command": "build_algorithm_comparison",
        "command_args": {"profiles": list(normalized_profiles), "seeds": int(seeds)},
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "seed_count": int(seeds),
        "algorithm_profiles": list(normalized_profiles),
        "ratchet_key_fields": ["case_group", "case_slug", "algorithm_profile", "algorithm_version", "seed"],
        "reference_diagnostics": build_reference_diagnostics(objective_name=OBJECTIVE_NAME),
        "rows": all_rows,
        "summary": summarize_comparison_rows(all_rows),
    }
    return payload


def _normalize_profiles(profiles: Sequence[str]) -> Tuple[str, ...]:
    out: List[str] = []
    for item in profiles:
        text = str(item or "").strip().lower()
        if text == "graph_ready":
            text = "graph_ready_v1"
        if text and text not in out:
            out.append(text)
    return tuple(out or DEFAULT_ALGORITHM_PROFILES)


def _run_seed_profiles(*, seed: int, profiles: Tuple[str, ...]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    real_profiles = [profile for profile in profiles if profile != "portfolio_all"]
    for profile in real_profiles:
        rows.append(_run_single_profile(profile=profile, seed=seed))
    if "portfolio_all" in profiles:
        rows.append(_portfolio_row(rows, seed=seed))
    return rows


def _run_single_profile(*, profile: str, seed: int) -> Dict[str, Any]:
    if profile == "greedy":
        return _baseline_row(seed=seed)
    if profile == "graph_ready_v1":
        return _graph_ready_v1_row(seed=seed)
    if profile == "graph_ready_v2_no_repair":
        return _graph_ready_v2_row(seed=seed, with_repair=False)
    if profile == "graph_ready_v2_with_repair":
        return _graph_ready_v2_row(seed=seed, with_repair=True)
    if profile == "local_search":
        return _local_search_row(seed=seed)
    if profile == "grasp_ig":
        return _grasp_ig_row(seed=seed)
    raise ValueError(f"unknown algorithm profile: {profile}")


def _baseline_setup() -> Tuple[Any, List[Any], Dict[str, Any], Dict[str, Any]]:
    scheduler = _scheduler()
    operations = graph_ready_benchmark_operations()
    batches = graph_ready_benchmark_batches()
    baseline = _baseline_candidate(scheduler=scheduler, operations=operations, batches=batches)
    return scheduler, operations, batches, baseline


def _baseline_row(*, seed: int) -> Dict[str, Any]:
    _scheduler_obj, _operations, _batches, baseline = _baseline_setup()
    return _row_from_candidate(
        candidate=baseline,
        profile="greedy",
        version="baseline_v1",
        seed=seed,
        evaluated_candidates=1,
        distinct_candidates=1,
        accepted_candidates=1,
        candidate_rejections={},
        status="passed",
    )


def _graph_ready_v1_row(*, seed: int) -> Dict[str, Any]:
    row = dict(run_graph_ready_real_sgs_case(seed=seed))
    row.update(
        {
            "schema_version": COMPARE_SCHEMA_VERSION,
            "algorithm_profile": "graph_ready_v1",
            "algorithm_version": "graph_ready_weight_grid_v1",
            "case_group": COMPARE_CASE_GROUP,
            "case_slug": COMPARE_CASE_SLUG,
            "accepted_candidates": int(row.get("accepted_distinct_candidates") or 0),
            "comparison_reference_status": "reference_diagnostics_attached",
        }
    )
    return row


def _graph_ready_v2_row(*, seed: int, with_repair: bool) -> Dict[str, Any]:
    row = dict(run_graph_ready_v2_real_sgs_case(seed=seed, with_repair=with_repair))
    row["comparison_reference_status"] = "reference_diagnostics_attached"
    return row


def _local_search_row(*, seed: int) -> Dict[str, Any]:
    scheduler, operations, batches, baseline = _baseline_setup()
    state = _state(profile="local_search", seed=seed)
    state.mark_candidate_evaluated(baseline, origin="baseline")
    state.mark_candidate_accepted(baseline, origin="baseline")
    clock = BenchmarkClock()
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    best = run_local_search(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
        time_budget_seconds=1,
        deadline=1001.0,
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
        start_dt=START_DT,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        dispatch_mode_cfg="sgs",
        dispatch_rule_cfg="slack",
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        clock=clock,
        rng_factory=random.Random,
        schedule_fn=_schedule_with_scheduler,
        graph_ready_context=None,
        search_report_state=state,
        valid_dispatch_rules=["slack"],
    )
    return _row_from_candidate(
        candidate=best or baseline,
        profile="local_search",
        version="vns_sa_v1",
        seed=seed,
        evaluated_candidates=int(state.evaluated_candidates),
        distinct_candidates=int(len(state.candidate_fingerprints)),
        accepted_candidates=int(state.accepted_candidates),
        candidate_rejections=dict(state.rejection_summary),
        candidate_output_fingerprints=sorted(state.candidate_fingerprints),
        accepted_output_fingerprints=sorted(state.accepted_fingerprints),
        status="passed",
    )


def _grasp_ig_row(*, seed: int) -> Dict[str, Any]:
    scheduler, operations, batches, baseline = _baseline_setup()
    state = _state(profile="grasp_ig", seed=seed)
    state.mark_candidate_evaluated(baseline, origin="baseline")
    state.mark_candidate_accepted(baseline, origin="baseline")
    clock = BenchmarkClock()
    attempts: List[Dict[str, Any]] = []
    trace: List[Dict[str, Any]] = []
    best = run_grasp_ig_candidates(
        algo_mode="improve",
        best=baseline,
        version=int(seed),
        candidate_construction=derive_grasp_ig_limits(1),
        scheduler=scheduler,
        algo_ops_to_schedule=operations,
        batches=batches,
        start_dt=START_DT,
        end_date=None,
        downtime_map={},
        seed_sr_list=[],
        base_strategy=SortStrategy.PRIORITY_FIRST,
        base_params={},
        build_order=lambda _strategy, _params: list(BASE_BATCH_ORDER),
        dispatch_rule_cfg="slack",
        valid_dispatch_rules=["slack"],
        batch_order_enabled=True,
        resource_pool=None,
        objective_name=OBJECTIVE_NAME,
        deadline=1001.0,
        attempts=attempts,
        improvement_trace=trace,
        optimizer_algo_stats=snapshot_algo_stats(scheduler),
        t_begin=1000.0,
        readiness_gate_enabled=False,
        strict_mode=True,
        graph_ready_context=None,
        clock=clock,
        rng_factory=random.Random,
        schedule_fn=_schedule_with_scheduler,
        search_report_state=state,
    )
    return _row_from_candidate(
        candidate=best or baseline,
        profile="grasp_ig",
        version="grasp_ig_v1",
        seed=seed,
        evaluated_candidates=int(state.evaluated_candidates),
        distinct_candidates=int(len(state.candidate_fingerprints)),
        accepted_candidates=int(state.accepted_candidates),
        candidate_rejections=dict(state.rejection_summary),
        candidate_output_fingerprints=sorted(state.candidate_fingerprints),
        accepted_output_fingerprints=sorted(state.accepted_fingerprints),
        status="passed",
    )


def _state(*, profile: str, seed: int) -> OptimizationSearchReportState:
    return OptimizationSearchReportState(
        algorithm_profile=profile,
        seed=int(seed),
        time_budget_seconds=1,
        objective_name=OBJECTIVE_NAME,
        started_at=1000.0,
        candidate_profile={"acceptance": "improve_only"},
        strict_mode=True,
    )


def _row_from_candidate(
    *,
    candidate: Dict[str, Any],
    profile: str,
    version: str,
    seed: int,
    evaluated_candidates: int,
    distinct_candidates: int,
    accepted_candidates: int,
    candidate_rejections: Dict[str, Any],
    status: str,
    candidate_output_fingerprints: Optional[Sequence[str]] = None,
    accepted_output_fingerprints: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    summary = candidate.get("summary")
    best_output_fingerprint = _candidate_output_fingerprint(candidate)
    candidate_fingerprints = _fingerprints_or_default(candidate_output_fingerprints, best_output_fingerprint)
    accepted_fingerprints = _fingerprints_or_default(accepted_output_fingerprints, best_output_fingerprint)
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "algorithm_profile": profile,
        "algorithm_version": version,
        "seed": int(seed),
        "time_budget_seconds": 1,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": _score_list(candidate.get("score")),
        "failed_ops": int(getattr(summary, "failed_ops", 0) or 0),
        "runtime_ms": int(candidate.get("runtime_ms") or 0),
        "evaluated_candidates": int(evaluated_candidates),
        "distinct_candidates": len(candidate_fingerprints),
        "accepted_candidates": int(accepted_candidates),
        "accepted_distinct_candidates": len(accepted_fingerprints),
        "candidate_rejections": dict(candidate_rejections or {}),
        "best_origin": str(candidate.get("candidate_origin") or profile),
        "candidate_origin": str(candidate.get("candidate_origin") or profile),
        "best_order": _result_order(candidate.get("results")),
        "best_output_fingerprint": best_output_fingerprint,
        "candidate_output_fingerprints": candidate_fingerprints,
        "accepted_output_fingerprints": accepted_fingerprints,
        "comparison_reference_status": "reference_diagnostics_attached",
        "status": status,
    }


def _fingerprints_or_default(values: Optional[Sequence[str]], default: str) -> List[str]:
    out = sorted({str(item) for item in list(values or []) if str(item)})
    return out or [str(default)]


def _portfolio_row(rows: Sequence[Dict[str, Any]], *, seed: int) -> Dict[str, Any]:
    if not rows:
        raise ValueError("portfolio_all requires at least one source row")
    invalid_sources = _invalid_score_sources(rows)
    failed_sources = _failed_sources(rows)
    shape_mismatch_sources = _shape_mismatch_sources(rows)
    eligible_rows = _eligible_portfolio_rows(rows)
    best = min(eligible_rows, key=lambda row: _score_tuple(row.get("objective_score"))) if eligible_rows else {}
    candidate_fingerprints = _output_fingerprint_union(rows, field="candidate_output_fingerprints")
    accepted_fingerprints = _output_fingerprint_union(rows, field="accepted_output_fingerprints")
    return {
        "schema_version": COMPARE_SCHEMA_VERSION,
        "case_group": COMPARE_CASE_GROUP,
        "case_slug": COMPARE_CASE_SLUG,
        "algorithm_profile": "portfolio_all",
        "algorithm_version": "posthoc_same_seed_v1",
        "seed": int(seed),
        "time_budget_seconds": 1,
        "objective_name": OBJECTIVE_NAME,
        "objective_score": list(best.get("objective_score") or []),
        "failed_ops": int(best.get("failed_ops") or 0),
        "runtime_ms": sum(int(row.get("runtime_ms") or 0) for row in rows),
        "evaluated_candidates": sum(int(row.get("evaluated_candidates") or 0) for row in rows),
        "distinct_candidates": len(candidate_fingerprints),
        "accepted_candidates": len(accepted_fingerprints),
        "accepted_distinct_candidates": len(accepted_fingerprints),
        "candidate_rejections": _merge_rejections(rows),
        "best_origin": f"{best.get('algorithm_profile')}:{best.get('best_origin')}" if best else "",
        "candidate_origin": f"portfolio_all:{best.get('algorithm_profile')}" if best else "portfolio_all:no_eligible_source",
        "best_order": list(best.get("best_order") or []),
        "best_output_fingerprint": str(best.get("best_output_fingerprint") or ""),
        "candidate_output_fingerprints": candidate_fingerprints,
        "accepted_output_fingerprints": accepted_fingerprints,
        "comparison_reference_status": "reference_diagnostics_attached",
        "invalid_objective_score_sources": invalid_sources,
        "failed_source_profiles": failed_sources,
        "objective_score_shape_mismatch_sources": shape_mismatch_sources,
        "status": "failed" if invalid_sources or failed_sources or shape_mismatch_sources or not eligible_rows else "passed",
    }


def _merge_rejections(rows: Sequence[Dict[str, Any]]) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for row in rows:
        for key, value in (row.get("candidate_rejections") or {}).items():
            merged[str(key)] = merged.get(str(key), 0) + int(value or 0)
    return merged


def _attach_comparisons(rows: List[Dict[str, Any]]) -> None:
    baseline = _find_profile(rows, "greedy")
    graph_ready_v1 = _find_profile(rows, "graph_ready_v1")
    portfolio = _find_profile(rows, "portfolio_all")
    for row in rows:
        row["comparison_to_current_baseline"] = _comparison(row, baseline, label="current_baseline")
        row["comparison_to_graph_ready_v1"] = _comparison(row, graph_ready_v1, label="graph_ready_v1")
        row["comparison_to_portfolio_best"] = _comparison(row, portfolio, label="portfolio_best")


def _find_profile(rows: Sequence[Dict[str, Any]], profile: str) -> Optional[Dict[str, Any]]:
    for row in rows:
        if row.get("algorithm_profile") == profile:
            return dict(row)
    return None


def _comparison(row: Dict[str, Any], reference: Optional[Dict[str, Any]], *, label: str) -> Dict[str, Any]:
    if reference is None:
        actual = _valid_score_tuple(row.get("objective_score"))
        return {
            "reference": label,
            "baseline_algorithm_profile": None,
            "baseline_value": [],
            "actual_value": list(actual or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "missing_reference_algorithm",
        }
    if row.get("status") != "passed":
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(_valid_score_tuple(reference.get("objective_score")) or ()),
            "actual_value": list(_valid_score_tuple(row.get("objective_score")) or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "actual_status_not_passed",
        }
    if reference.get("status") != "passed":
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(_valid_score_tuple(reference.get("objective_score")) or ()),
            "actual_value": list(_valid_score_tuple(row.get("objective_score")) or ()),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "reference_status_not_passed",
        }
    actual = _valid_score_tuple(row.get("objective_score"))
    baseline = _valid_score_tuple(reference.get("objective_score"))
    if actual is None:
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline or ()),
            "actual_value": [],
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "invalid_actual_objective_score",
        }
    if baseline is None:
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": [],
            "actual_value": list(actual),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "invalid_reference_objective_score",
        }
    if len(actual) != len(baseline):
        return {
            "reference": label,
            "baseline_algorithm_profile": reference.get("algorithm_profile"),
            "baseline_value": list(baseline),
            "actual_value": list(actual),
            "primary_delta": None,
            "status": "not_comparable",
            "reason": "objective_score_shape_mismatch",
        }
    status = "same"
    if actual < baseline:
        status = "improved"
    elif actual > baseline:
        status = "degraded"
    return {
        "reference": label,
        "baseline_algorithm_profile": reference.get("algorithm_profile"),
        "baseline_value": list(baseline),
        "actual_value": list(actual),
        "primary_delta": _first_changed_delta(actual, baseline),
        "status": status,
    }


def _score_tuple(value: Any) -> Tuple[float, ...]:
    score = _valid_score_tuple(value)
    return score if score is not None else (float("inf"),)


def _valid_score_tuple(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (list, tuple)):
        return None
    if not value:
        return None
    score: List[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        number = float(item)
        if not math.isfinite(number):
            return None
        score.append(number)
    return tuple(score)


def _eligible_portfolio_rows(rows: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    expected_len = _expected_score_length(rows)
    if expected_len is None:
        return []
    return [
        row
        for row in rows
        if row.get("status") == "passed"
        and (score := _valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) == expected_len
    ]


def _expected_score_length(rows: Sequence[Dict[str, Any]]) -> Optional[int]:
    lengths = [
        len(score)
        for row in rows
        if row.get("status") == "passed" and (score := _valid_score_tuple(row.get("objective_score"))) is not None
    ]
    return max(lengths) if lengths else None


def _invalid_score_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if _valid_score_tuple(row.get("objective_score")) is None
    ]


def _failed_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if row.get("status") != "passed"
    ]


def _shape_mismatch_sources(rows: Sequence[Dict[str, Any]]) -> List[str]:
    expected_len = _expected_score_length(rows)
    if expected_len is None:
        return []
    return [
        str(row.get("algorithm_profile") or "")
        for row in rows
        if (score := _valid_score_tuple(row.get("objective_score"))) is not None
        and len(score) != expected_len
    ]


def _first_changed_delta(actual: Tuple[float, ...], baseline: Tuple[float, ...]) -> float:
    for actual_item, baseline_item in zip(actual, baseline):
        delta = float(actual_item) - float(baseline_item)
        if abs(delta) > 1e-9:
            return delta
    return 0.0


def _git_commit(repo_root: Path) -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _dirty_worktree(repo_root: Path) -> bool:
    try:
        out = subprocess.check_output(["git", "status", "--short"], cwd=str(repo_root), text=True)
    except (OSError, subprocess.CalledProcessError):
        return True
    return bool(out.strip())


def _candidate_output_fingerprint(candidate: Dict[str, Any]) -> str:
    return build_candidate_fingerprint(
        candidate,
        objective_name=OBJECTIVE_NAME,
        parent_fingerprint=None,
        seen_output_fingerprints=set(),
    ).output_fingerprint


def _output_fingerprint_union(rows: Sequence[Dict[str, Any]], *, field: str) -> List[str]:
    fingerprints = set()
    for row in rows:
        added = False
        for item in list(row.get(field) or []):
            text = str(item or "").strip()
            if text:
                fingerprints.add(text)
                added = True
        if not added and row.get("best_output_fingerprint"):
            fingerprints.add(str(row["best_output_fingerprint"]))
    return sorted(fingerprints)


__all__ = [
    "COMPARE_SCHEMA_VERSION",
    "DEFAULT_ALGORITHM_PROFILES",
    "build_algorithm_comparison",
    "compare_to_algorithm_baseline",
    "summarize_comparison_rows",
]
