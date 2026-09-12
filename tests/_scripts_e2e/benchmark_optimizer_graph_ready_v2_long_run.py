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

from tests._scripts_e2e.benchmark_optimizer_compare_algorithms import (  # noqa: E402
    _check_baseline,
    _preflight_baseline,
    _proof_check,
    _write_baseline,
    _write_diagnostic,
)
from tests._support.optimizer_graph_ready_v2_long_run import (  # noqa: E402
    DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES,
    build_graph_ready_v2_long_run,
)

DEFAULT_LONG_RUN_BASELINE = Path(".codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-long-run-baseline.json")
DEFAULT_LONG_RUN_OUTPUT = Path("evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_graph_ready_v2_long_run.json")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GraphReady v2 long-run evidence.")
    parser.add_argument("--seeds", type=int, default=10, help="seed count; must be at least 10")
    parser.add_argument("--workers", type=int, choices=(1,), default=1, help="one worker preserves wall-clock comparability")
    parser.add_argument("--profiles", default=",".join(DEFAULT_GRAPH_READY_V2_LONG_RUN_PROFILES))
    parser.add_argument("--output", default=str(DEFAULT_LONG_RUN_OUTPUT))
    parser.add_argument("--baseline", default=str(DEFAULT_LONG_RUN_BASELINE))
    parser.add_argument("--no-write", action="store_true", help="print only; do not write ignored output")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--check-baseline", action="store_true", help="compare current output with baseline")
    action.add_argument("--update-baseline", action="store_true", help="write a passed, clean long-run baseline")
    parser.add_argument(
        "--allow-dirty-proof",
        action="store_true",
        help="allow dirty-worktree output only as unbound proof, never as clean proof",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.update_baseline and args.allow_dirty_proof:
        parser.error("--allow-dirty-proof is diagnostic only and cannot be used with --update-baseline")
    if int(args.seeds) < 10:
        print(json.dumps({"status": "failed", "reason": "seeds_below_long_run_minimum"}, ensure_ascii=False, sort_keys=True))
        return 2
    baseline_path = _repo_path(Path(args.baseline))
    if args.update_baseline or args.check_baseline:
        preflight = _preflight_baseline(baseline_path, allow_dirty=args.allow_dirty_proof, updating=args.update_baseline)
        if preflight is not None:
            print(json.dumps({"baseline_write" if args.update_baseline else "baseline_check": preflight}, ensure_ascii=False, sort_keys=True))
            return 1
    profiles = [item.strip() for item in str(args.profiles or "").split(",") if item.strip()]
    payload = build_graph_ready_v2_long_run(profiles=profiles, seeds=int(args.seeds), workers=args.workers)
    result = {"long_run": payload}
    status = str(payload.get("status") or "failed")
    result["proof_check"] = _proof_check(payload, allow_dirty=True)
    if result["proof_check"]["status"] != "passed":
        status = "failed"

    if args.update_baseline:
        write_result = _write_baseline(payload, baseline_path=baseline_path, allow_dirty=bool(args.allow_dirty_proof))
        result["baseline_write"] = write_result
        if write_result["status"] != "passed":
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
    elif args.check_baseline:
        check_result = _check_baseline(payload, baseline_path=baseline_path, allow_dirty=bool(args.allow_dirty_proof))
        result["baseline_check"] = check_result
        if check_result.get("status") != "passed":
            status = "failed"

    if not args.no_write and not args.update_baseline:
        output_path = _repo_path(Path(args.output))
        result["diagnostic_write"] = _write_diagnostic(payload, output_path=output_path, baseline_path=baseline_path)
        if result["diagnostic_write"]["status"] != "passed":
            status = "failed"

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
