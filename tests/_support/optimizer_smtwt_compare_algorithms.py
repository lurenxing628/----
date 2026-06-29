"""Same-objective SMTWT algorithm comparison for optimizer benchmarks."""

from __future__ import annotations

import subprocess
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from tests._support.optimizer_benchmark_grading import smtwt_overdue_case
from tests._support.optimizer_benchmark_loaders import load_smtwt_instances, moore_hodgson_min_tardy
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
    normalized_profiles = normalize_profiles(profiles)
    rows = _build_rows(
        profiles=normalized_profiles,
        sizes=sizes,
        seeds=int(seeds),
        limit_per_size=limit_per_size,
        time_budget_seconds=int(time_budget_seconds),
        workers=int(workers),
    )
    return _payload(
        rows=rows,
        profiles=normalized_profiles,
        sizes=sizes,
        seeds=int(seeds),
        limit_per_size=limit_per_size,
        workers=int(workers),
    )


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
    if int(workers) <= 1 or len(tasks) <= 1:
        return _flatten(_run_case_task(task) for task in tasks)
    with ProcessPoolExecutor(max_workers=min(int(workers), len(tasks))) as executor:
        return _flatten(executor.map(_run_case_task, tasks))


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
    context = build_case_context(case=case, time_budget_seconds=time_budget_seconds)
    rows = [_run_profile(profile=profile, context=context, optimum=optimum, seed=seed) for profile in profiles if profile != "portfolio_all"]
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
    dirty_worktree = _dirty_worktree(Path.cwd())
    return {
        "schema_version": SMTWT_COMPARE_SCHEMA_VERSION,
        "status": "passed" if rows and all(row.get("status") == "passed" for row in rows) else "failed",
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "git_commit": _git_commit(Path.cwd()),
        "dirty_worktree": dirty_worktree,
        "proof_binding_status": "unbound_dirty_worktree" if dirty_worktree else "clean_worktree",
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


__all__ = ["DEFAULT_SMTWT_PROFILES", "build_smtwt_algorithm_comparison"]
