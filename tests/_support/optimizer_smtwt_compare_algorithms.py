"""Same-objective SMTWT algorithm comparison for optimizer benchmarks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tests._support.optimizer_benchmark_grading import smtwt_overdue_case
from tests._support.optimizer_benchmark_loaders import load_smtwt_instances, moore_hodgson_min_tardy
from tests._support.optimizer_compare_algorithms_provenance import (
    MEASUREMENT,
    capture_source,
    machine_metadata,
    require_serial_workers,
    source_binding,
)
from tests._support.optimizer_smtwt_compare_common import (
    DEFAULT_SMTWT_PROFILES,
    SMTWT_COMPARE_SCHEMA_VERSION,
    SMTWT_OBJECTIVE_NAME,
    normalize_profiles,
)
from tests._support.optimizer_smtwt_compare_context import build_case_context
from tests._support.optimizer_smtwt_compare_graph import run_graph_profile
from tests._support.optimizer_smtwt_compare_report import (
    attach_case_comparisons,
    pairwise_vs,
    portfolio_row,
    summarize_rows,
)
from tests._support.optimizer_smtwt_compare_runners import run_standard_profile


def build_smtwt_algorithm_comparison(
    *,
    profiles: Sequence[str],
    sizes: Sequence[int],
    seeds: int = 1,
    limit_per_size: Optional[int] = None,
    time_budget_seconds: int = 1,
    workers: int = 1,
) -> Dict[str, Any]:
    require_serial_workers(workers)
    source_before = capture_source(Path.cwd())
    normalized_profiles = normalize_profiles(profiles)
    rows = _build_rows(
        profiles=normalized_profiles,
        sizes=sizes,
        seeds=int(seeds),
        limit_per_size=limit_per_size,
        time_budget_seconds=int(time_budget_seconds),
        workers=int(workers),
    )
    payload = _payload(
        rows=rows,
        profiles=normalized_profiles,
        sizes=sizes,
        seeds=int(seeds),
        limit_per_size=limit_per_size,
        workers=int(workers),
    )
    source_after = capture_source(Path.cwd())
    payload.update({
        "source_before": source_before, "source_after": source_after,
        "git_commit": source_after["head"],
        "dirty_worktree": not source_before["worktree_clean"] or not source_after["worktree_clean"],
        "proof_binding_status": source_binding(source_before, source_after),
        "measurement": dict(MEASUREMENT), "machine": machine_metadata(),
    })
    return payload


def _build_rows(
    *,
    profiles: Tuple[str, ...],
    sizes: Sequence[int],
    seeds: int,
    limit_per_size: Optional[int],
    time_budget_seconds: int,
    workers: int,
) -> List[Dict[str, Any]]:
    tasks = _build_tasks(
        profiles=profiles,
        sizes=sizes,
        seeds=seeds,
        limit_per_size=limit_per_size,
        time_budget_seconds=time_budget_seconds,
    )
    require_serial_workers(workers)
    return _flatten(_run_case_task(task) for task in tasks)


def _build_tasks(
    *,
    profiles: Tuple[str, ...],
    sizes: Sequence[int],
    seeds: int,
    limit_per_size: Optional[int],
    time_budget_seconds: int,
) -> List[Tuple[Any, int, Tuple[str, ...], int]]:
    tasks: List[Tuple[Any, int, Tuple[str, ...], int]] = []
    for size in [int(item) for item in sizes]:
        for instance in _instances_for_size(size=size, limit_per_size=limit_per_size):
            for seed in range(int(seeds)):
                tasks.append((instance, seed, profiles, int(time_budget_seconds)))
    return tasks


def _run_case_task(task: Tuple[Any, int, Tuple[str, ...], int]) -> List[Dict[str, Any]]:
    instance, seed, profiles, time_budget_seconds = task
    return _run_case_profiles(instance=instance, seed=seed, profiles=profiles, time_budget_seconds=time_budget_seconds)


def _flatten(chunks: Any) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for chunk in chunks:
        rows.extend(chunk)
    return rows


def _run_case_profiles(*, instance: Any, seed: int, profiles: Tuple[str, ...], time_budget_seconds: int) -> List[Dict[str, Any]]:
    case = smtwt_overdue_case(instance)
    optimum = moore_hodgson_min_tardy(instance.processing_times, instance.due_dates)
    rows = []
    for profile in profiles:
        if profile == "portfolio_all":
            continue
        # Rebuild each baseline inside that algorithm's own clock and budget.
        context = build_case_context(case=case, time_budget_seconds=time_budget_seconds)
        rows.append(_run_profile(profile=profile, context=context, optimum=optimum, seed=seed))
    if "portfolio_all" in profiles:
        rows.append(portfolio_row(rows, seed=seed, optimum=optimum))
    attach_case_comparisons(rows)
    return rows


def _run_profile(*, profile: str, context: Dict[str, Any], optimum: int, seed: int) -> Dict[str, Any]:
    if profile in {"greedy", "local_search", "grasp_ig"}:
        return run_standard_profile(profile=profile, context=context, optimum=optimum, seed=seed)
    if profile.startswith("graph_ready"):
        return run_graph_profile(profile=profile, context=context, optimum=optimum, seed=seed)
    raise ValueError(f"unknown algorithm profile: {profile}")


def _instances_for_size(*, size: int, limit_per_size: Optional[int]) -> List[Any]:
    instances = load_smtwt_instances(int(size))
    return instances if limit_per_size is None else instances[: int(limit_per_size)]


def _payload(
    *,
    rows: List[Dict[str, Any]],
    profiles: Tuple[str, ...],
    sizes: Sequence[int],
    seeds: int,
    limit_per_size: Optional[int],
    workers: int,
) -> Dict[str, Any]:
    return {
        "schema_version": SMTWT_COMPARE_SCHEMA_VERSION,
        "status": "passed" if rows and all(row.get("status") == "passed" for row in rows) else "failed",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "case_group": "smtwt_overdue",
        "objective_name": SMTWT_OBJECTIVE_NAME,
        "sizes": [int(item) for item in sizes],
        "seed_count": int(seeds),
        "limit_per_size": limit_per_size,
        "workers": int(workers),
        "algorithm_profiles": list(profiles),
        "ratchet_key_fields": ["case_group", "case_slug", "algorithm_profile", "algorithm_version", "seed"],
        "comparison_scope": (
            "SMTWT single-machine shape check; wins/ties/losses use full objective_score, "
            "Moore-Hodgson optimum covers overdue_count primary component only; not an APS graph/multi-machine optimum proof"
        ),
        "degenerate_benchmark_notice": (
            "SMTWT rows have no graph precedence and no multi-machine APS resource graph; "
            "they compare algorithm shape only and must not be reported as APS min_overdue global optimum proof."
        ),
        "rows": rows,
        "summary": summarize_rows(rows),
        "pairwise_vs_graph_ready_v2": pairwise_vs(rows, subject="graph_ready_v2_no_repair"),
    }


__all__ = ["DEFAULT_SMTWT_PROFILES", "build_smtwt_algorithm_comparison"]
