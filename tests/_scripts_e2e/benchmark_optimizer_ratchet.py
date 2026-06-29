#!/usr/bin/env python3
"""Build or check optimizer benchmark ratchet snapshots."""

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

from tests._support.optimizer_benchmark_ratchet import (  # noqa: E402
    DEFAULT_BASELINE,
    build_light_ratchet_snapshot,
    compare_to_baseline,
    load_baseline,
    write_baseline,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run optimizer benchmark ratchet checks.")
    parser.add_argument("--tier", choices=("light",), default="light", help="benchmark tier to run")
    parser.add_argument("--baseline", default=str(DEFAULT_BASELINE), help="ratchet baseline path")
    parser.add_argument("--update-baseline", action="store_true", help="write current snapshot as the tracked baseline")
    parser.add_argument("--check-baseline", action="store_true", help="compare current snapshot with the baseline")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    snapshot = build_light_ratchet_snapshot(repo_root=REPO_ROOT)
    baseline_path = Path(args.baseline)
    if not baseline_path.is_absolute():
        baseline_path = REPO_ROOT / baseline_path

    result = {"snapshot": snapshot}
    status = snapshot.get("status")
    if args.update_baseline:
        write_baseline(baseline_path, snapshot)
        result["baseline_written"] = str(baseline_path.relative_to(REPO_ROOT))
    elif args.check_baseline:
        baseline = load_baseline(baseline_path)
        if baseline is None:
            result["baseline_check"] = {"status": "failed", "failure_count": 1, "failures": [{"reason": "missing_baseline"}]}
            status = "failed"
        else:
            comparison = compare_to_baseline(snapshot, baseline)
            result["baseline_check"] = comparison
            status = comparison["status"]

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
