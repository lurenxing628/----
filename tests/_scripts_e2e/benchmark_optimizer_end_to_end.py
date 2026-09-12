#!/usr/bin/env python3
"""Explicit serial optimizer benchmark; snapshots are not full-gate or general optimality proof."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests._support.optimizer_end_to_end_cases import OBJECTIVES, SCENARIOS
from tests._support.optimizer_end_to_end_compare import compare_end_to_end_matrices
from tests._support.optimizer_end_to_end_io import DIAGNOSTIC_DIR, read_snapshot, update_baseline, write_diagnostic
from tests._support.optimizer_end_to_end_runner import DEFAULT_RUN_CONFIG, build_end_to_end_matrix


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="explicitly measure complete optimizer entry points serially")
    for key, value in DEFAULT_RUN_CONFIG.items():
        run.add_argument("--" + key.replace("_", "-"), type=type(value), default=value)
    run.add_argument("--scenario", action="append", choices=SCENARIOS, help="repeat for a diagnostic subset; default: all")
    run.add_argument("--objective", action="append", choices=OBJECTIVES, help="repeat for a diagnostic subset; default: all")
    run.add_argument("--output", type=Path, default=REPO_ROOT / DIAGNOSTIC_DIR / "snapshot.json")
    check = commands.add_parser("check", help="validate a saved snapshot without running the optimizer")
    check.add_argument("--snapshot", type=Path, required=True)
    compare = commands.add_parser("compare", help="compare saved snapshots under equal machine/configuration")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--actual", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    update = commands.add_parser("update-baseline", help="promote native-count full coverage with a live clean source receipt")
    update.add_argument("--snapshot", type=Path, required=True)
    update.add_argument("--baseline", type=Path, required=True)
    for command in (compare, update):
        command.add_argument("--runtime-ratio", type=float, default=3.0)
        command.add_argument("--runtime-slack-ms", type=float, default=250.0)
    return parser


def main(argv=None):
    args = build_arg_parser().parse_args(argv)
    try:
        if args.command == "run":
            config = {key: getattr(args, key) for key in DEFAULT_RUN_CONFIG}
            snapshot = build_end_to_end_matrix(config, args.scenario, args.objective)
            write_diagnostic(args.output, snapshot, REPO_ROOT)
            result = {
                "status": snapshot["status"], "output": str(args.output), "proof_binding": snapshot["proof_binding"],
                "claim": snapshot["claim"], "coverage": snapshot["coverage"], "measurement": snapshot["measurement"],
                "cases": [{key: row[key] for key in (
                    "case_id", "operation_count", "runtime_ms", "decode_count", "optimizer_call_count",
                    "first_improvement_ms", "selected_candidate_key", "status", "errors",
                )} for row in snapshot["cases"]],
            }
        elif args.command == "check":
            snapshot = read_snapshot(args.snapshot)
            result = {"status": "passed", "snapshot": str(args.snapshot), "proof_binding": snapshot["proof_binding"],
                      "claim": "validated_snapshot_not_full_quality_gate_proof", "coverage": snapshot["coverage"],
                      "measurement": snapshot["measurement"]}
        elif args.command == "compare":
            result = compare_end_to_end_matrices(read_snapshot(args.baseline), read_snapshot(args.actual),
                                                args.runtime_ratio, args.runtime_slack_ms)
            if args.output:
                write_diagnostic(args.output, result, REPO_ROOT)
        else:
            if args.snapshot.resolve() == args.baseline.resolve():
                raise ValueError("snapshot and baseline paths must differ")
            update_baseline(read_snapshot(args.snapshot), args.baseline, REPO_ROOT, args.runtime_ratio, args.runtime_slack_ms)
            result = {"status": "passed", "baseline": str(args.baseline),
                      "claim": "end_to_end_baseline_not_full_quality_gate_proof"}
    except (ValueError, TypeError, KeyError, OSError, OverflowError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
