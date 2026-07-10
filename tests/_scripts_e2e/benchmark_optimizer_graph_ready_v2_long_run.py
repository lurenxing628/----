#!/usr/bin/env python3
"""Run GraphReady v2 long-run evidence with the shared comparison matrix."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Sequence


def find_repo_root() -> Path:
    here = Path(__file__).resolve()
    for probe in [here.parent] + list(here.parents):
        if (probe / "app.py").exists() and (probe / "schema.sql").exists():
            return probe
    raise RuntimeError("repo root not found")


REPO_ROOT = find_repo_root()
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests._support.benchmark_parallel import DEFAULT_BENCHMARK_WORKERS, positive_worker_count  # noqa: E402
from tests._support.optimizer_compare_algorithms import compare_to_algorithm_baseline  # noqa: E402
from tests._support.optimizer_graph_ready_v2_long_run import (  # noqa: E402
    DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES,
    build_graph_ready_v2_long_run,
)

DEFAULT_LONG_RUN_BASELINE = Path(".codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-long-run-baseline.json")
DEFAULT_LONG_RUN_OUTPUT = Path("evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_graph_ready_v2_long_run.json")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GraphReady v2 long-run evidence.")
    parser.add_argument("--seeds", type=int, default=10, help="seed count; must be at least 10")
    parser.add_argument("--workers", type=int, default=DEFAULT_BENCHMARK_WORKERS, help="parallel worker processes")
    parser.add_argument("--profiles", default=",".join(DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES))
    parser.add_argument("--output", default=str(DEFAULT_LONG_RUN_OUTPUT))
    parser.add_argument("--baseline", default=str(DEFAULT_LONG_RUN_BASELINE))
    parser.add_argument("--no-write", action="store_true", help="print only; do not write ignored output")
    parser.add_argument("--check-baseline", action="store_true", help="compare current output with baseline")
    parser.add_argument("--update-baseline", action="store_true", help="write current long-run baseline")
    parser.add_argument(
        "--allow-dirty-proof",
        action="store_true",
        help="allow dirty-worktree output only as unbound proof, never as clean proof",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    if int(args.seeds) < 10:
        print(json.dumps({"status": "failed", "reason": "seeds_below_long_run_minimum"}, ensure_ascii=False, sort_keys=True))
        return 2
    profiles = [item.strip() for item in str(args.profiles or "").split(",") if item.strip()]
    workers = positive_worker_count(args.workers)
    payload = build_graph_ready_v2_long_run(profiles=profiles, seeds=int(args.seeds), workers=workers)
    result = {"long_run": payload}
    status = str(payload.get("status") or "failed")
    baseline_path = _repo_path(Path(args.baseline))

    if args.update_baseline:
        write_result = _write_baseline(payload, baseline_path=baseline_path, allow_dirty=bool(args.allow_dirty_proof))
        result["baseline_write"] = write_result
        if write_result["status"] != "passed":
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
    elif args.check_baseline:
        check_result = _check_baseline(payload, baseline_path=baseline_path, allow_dirty=bool(args.allow_dirty_proof))
        result["baseline_check"] = check_result
        status = str(check_result.get("status") or "failed")

    if not args.no_write and not args.update_baseline:
        output_path = _repo_path(Path(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["output_written"] = _display_path(output_path)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _write_baseline(payload: dict, *, baseline_path: Path, allow_dirty: bool) -> dict:
    if payload.get("dirty_worktree") is True and not allow_dirty:
        return {
            "status": "failed",
            "reason": "dirty_actual_worktree",
            "proof_binding_status": "unbound_dirty_worktree",
        }
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "status": "passed",
        "path": _display_path(baseline_path),
        "proof_binding_status": payload.get("proof_binding_status"),
    }


def _check_baseline(payload: dict, *, baseline_path: Path, allow_dirty: bool) -> dict:
    if not baseline_path.exists():
        return {"status": "failed", "failure_count": 1, "failures": [{"reason": "missing_baseline"}]}
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    actual_comparison = _comparison_payload(payload)
    baseline_comparison = _comparison_payload(baseline)
    return compare_to_algorithm_baseline(
        actual_comparison,
        baseline_comparison,
        require_clean_proof=not allow_dirty,
    )


def _comparison_payload(payload: dict) -> dict:
    comparison = payload.get("comparison")
    if isinstance(comparison, dict):
        return comparison
    return payload


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
