#!/usr/bin/env python3
"""Long-run graph-ready optimizer benchmark evidence.

Default output is ignored by git: evidence/QualityGate/long_gate/optimizer_benchmark/.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("repo root not found")


REPO_ROOT = find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests._support.benchmark_parallel import (  # noqa: E402
    DEFAULT_BENCHMARK_WORKERS,
    parallel_map_ordered,
    positive_worker_count,
)
from tests._support.optimizer_graph_ready_benchmark import run_graph_ready_real_sgs_case  # noqa: E402


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run graph-ready optimizer long benchmark.")
    parser.add_argument("--seeds", type=int, default=10, help="number of seeds; must be at least 10")
    parser.add_argument("--workers", type=int, default=DEFAULT_BENCHMARK_WORKERS, help="parallel worker processes")
    parser.add_argument("--output-dir", default="evidence/QualityGate/long_gate/optimizer_benchmark")
    parser.add_argument("--no-write", action="store_true", help="only print JSON to stdout")
    return parser


def run_seed(seed: int) -> Dict[str, Any]:
    row = run_graph_ready_real_sgs_case(seed=int(seed))
    evaluated = max(int(row.get("evaluated_candidates") or 0), 1)
    same = int(row.get("same_fingerprint_rejections") or 0)
    row["duplicate_candidate_rate"] = round(float(same) / float(evaluated), 6)
    row["candidate_rejection_rate"] = round(float(sum((row.get("candidate_rejections") or {}).values())) / float(evaluated), 6)
    return row


def aggregate(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    first_scores = [float(row["objective_score"][0]) for row in rows if row.get("objective_score")]
    duplicate_rates = [float(row["duplicate_candidate_rate"]) for row in rows]
    rejection_rates = [float(row["candidate_rejection_rate"]) for row in rows]
    return {
        "seed_count": len(rows),
        "mean_failed_ops": statistics.mean(first_scores) if first_scores else None,
        "worst_failed_ops": max(first_scores) if first_scores else None,
        "stdev_failed_ops": statistics.pstdev(first_scores) if len(first_scores) > 1 else 0.0,
        "mean_duplicate_candidate_rate": statistics.mean(duplicate_rates) if duplicate_rates else 0.0,
        "mean_candidate_rejection_rate": statistics.mean(rejection_rates) if rejection_rates else 0.0,
        "min_distinct_candidates": min((int(row.get("distinct_candidates") or 0) for row in rows), default=0),
        "min_accepted_distinct_candidates": min((int(row.get("accepted_distinct_candidates") or 0) for row in rows), default=0),
    }


def write_reports(output_dir: Path, payload: Dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "optimizer_long_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Optimizer Long Run", "", f"- status: {payload['status']}", f"- seeds: {payload['aggregate']['seed_count']}"]
    lines.append(f"- workers: {payload['workers']}")
    lines.append(f"- mean duplicate rate: {payload['aggregate']['mean_duplicate_candidate_rate']}")
    lines.append(f"- mean rejection rate: {payload['aggregate']['mean_candidate_rejection_rate']}")
    (output_dir / "optimizer_long_run.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    if int(args.seeds) < 10:
        raise SystemExit("--seeds must be at least 10")
    workers = positive_worker_count(args.workers)
    rows = parallel_map_ordered(run_seed, range(int(args.seeds)), workers=workers)
    payload = {
        "schema_version": 1,
        "status": "passed" if rows and all(row.get("status") == "passed" for row in rows) else "failed",
        "tier": "long_run",
        "workers": workers,
        "cases": rows,
        "aggregate": aggregate(rows),
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.no_write:
        output_dir = Path(args.output_dir)
        if not output_dir.is_absolute():
            output_dir = REPO_ROOT / output_dir
        write_reports(output_dir, payload)
    return 0 if payload["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
