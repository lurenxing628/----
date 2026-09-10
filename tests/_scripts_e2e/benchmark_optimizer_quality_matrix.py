#!/usr/bin/env python3
"""Production optimizer quality matrix; run serially, save diagnostics, compare or promote."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests._support.optimizer_quality_matrix import DEFAULT_RUN_CONFIG, build_quality_matrix
from tests._support.optimizer_quality_matrix_compare import compare_quality_matrices
from tests._support.optimizer_quality_matrix_io import DIAGNOSTIC_DIR, read_snapshot, update_baseline, write_diagnostic


def build_arg_parser():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("run", help="run all eight cases using real wall clock and temporary memory DBs")
    for key, value in DEFAULT_RUN_CONFIG.items():
        run.add_argument("--" + key.replace("_", "-"), type=type(value), default=value)
    run.add_argument("--output", type=Path, default=REPO_ROOT / DIAGNOSTIC_DIR / "snapshot.json")
    compare = commands.add_parser("compare", help="compare two saved matrices, including full schedule validation")
    compare.add_argument("--baseline", type=Path, required=True)
    compare.add_argument("--actual", type=Path, required=True)
    compare.add_argument("--output", type=Path)
    update = commands.add_parser("update-baseline", help="promote a passed clean same-HEAD snapshot only")
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
            snapshot = build_quality_matrix(REPO_ROOT, config)
            write_diagnostic(args.output, snapshot, REPO_ROOT)
            result = {"status": snapshot["status"], "output": str(args.output), "proof_binding": snapshot["proof_binding"],
                      "cases": [{key: row[key] for key in ("case_id", "operation_count", "runtime_ms", "counts", "status", "errors")}
                                for row in snapshot["cases"]]}
        elif args.command == "compare":
            result = compare_quality_matrices(read_snapshot(args.baseline), read_snapshot(args.actual),
                                              args.runtime_ratio, args.runtime_slack_ms)
            if args.output:
                write_diagnostic(args.output, result, REPO_ROOT)
        else:
            if args.snapshot.resolve() == args.baseline.resolve():
                raise ValueError("snapshot and baseline paths must differ")
            update_baseline(read_snapshot(args.snapshot), args.baseline, REPO_ROOT, args.runtime_ratio, args.runtime_slack_ms)
            result = {"status": "passed", "baseline": str(args.baseline), "claim": "matrix_baseline_not_full_gate_proof"}
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=True))
    return 0 if result["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
