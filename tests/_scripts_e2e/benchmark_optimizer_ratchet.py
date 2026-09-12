#!/usr/bin/env python3
"""Build or check optimizer benchmark ratchet snapshots."""

from __future__ import annotations

import argparse
import json
import subprocess
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

from tests._support.optimizer_benchmark_ratchet import (  # noqa: E402
    DEFAULT_BASELINE,
    baseline_update_failures,
    build_light_ratchet_snapshot,
    compare_to_baseline,
    load_baseline,
    snapshot_protocol_failures,
    write_baseline,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run optimizer benchmark ratchet checks.")
    parser.add_argument("--tier", choices=("light",), default="light", help="benchmark tier to run")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="ratchet baseline path")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update-baseline", action="store_true", help="write a passed, clean snapshot as the baseline")
    action.add_argument("--check-baseline", action="store_true", help="compare current snapshot with the baseline")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    baseline_path = Path(args.baseline)
    if not baseline_path.is_absolute():
        baseline_path = REPO_ROOT / baseline_path
    baseline, preflight = _preflight_baseline(args, baseline_path)
    if preflight is not None:
        key = "baseline_update" if args.update_baseline else "baseline_check"
        print(json.dumps({key: preflight}, ensure_ascii=False, indent=2, sort_keys=True))
        return 1
    snapshot = build_light_ratchet_snapshot(repo_root=REPO_ROOT)

    result = {"snapshot": snapshot}
    status = snapshot.get("status")
    if args.update_baseline:
        failures = baseline_update_failures(snapshot)
        if failures:
            result["baseline_update"] = {"status": "failed", "failures": failures}
            status = "failed"
        else:
            try:
                write_baseline(baseline_path, snapshot, repo_root=REPO_ROOT)
                result["baseline_written"] = str(baseline_path)
            except (ValueError, OSError, subprocess.SubprocessError) as exc:
                result["baseline_update"] = _failed("baseline_update_rejected", detail=str(exc))
                status = "failed"
    elif args.check_baseline:
        comparison = compare_to_baseline(snapshot, baseline)
        result["baseline_check"] = comparison
        status = comparison["status"]

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


def _failed(reason: str, **details) -> dict:
    return {"status": "failed", "reason": reason, "failure_count": 1, "failures": [{"reason": reason, **details}]}


def _preflight_baseline(args, path: Path):
    if not (args.check_baseline or args.update_baseline):
        return None, None
    try:
        baseline = load_baseline(path)
    except (OSError, ValueError) as exc:
        return None, _failed("invalid_baseline", detail=str(exc))
    if baseline is None:
        return None, _failed("missing_baseline") if args.check_baseline else None
    failures = snapshot_protocol_failures(baseline, label="baseline")
    if failures:
        return baseline, {"status": "failed", "failure_count": len(failures), "failures": failures}
    comparison = compare_to_baseline(baseline, baseline)
    return baseline, comparison if comparison["status"] != "passed" else None


if __name__ == "__main__":
    raise SystemExit(main())
