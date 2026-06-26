#!/usr/bin/env python3
"""Run the scheduler optimizer proof harness without writing tracked evidence by default."""

from __future__ import annotations

import argparse
import json
import os
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

from core.services.scheduler.run.optimizer_proof_harness import (  # noqa: E402
    render_optimizer_proof_report,
    run_optimizer_proof_harness,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run tiny oracle/lower-bound scheduler optimizer proof checks.",
    )
    parser.add_argument(
        "--require-optimal",
        action="store_true",
        help="fail when the decoded scheduler result does not match the tiny exact oracle.",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="explicitly write a tracked Markdown report. Default only prints JSON to stdout.",
    )
    parser.add_argument(
        "--include-diagnostics",
        action="store_true",
        help="print full reference diagnostics to stdout. Default stdout is public summary only.",
    )
    parser.add_argument(
        "--report-path",
        default=os.path.join("evidence", "Benchmark", "optimizer_proof_harness_report.md"),
        help="report path used only with --write-report.",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    payload = run_optimizer_proof_harness(require_optimal=bool(args.require_optimal))
    stdout_payload = payload if args.include_diagnostics else payload["public"]
    print(json.dumps(stdout_payload, ensure_ascii=False, sort_keys=True, indent=2))
    if args.write_report:
        report_path = Path(args.report_path)
        if not report_path.is_absolute():
            report_path = REPO_ROOT / report_path
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_optimizer_proof_report(payload), encoding="utf-8")
        print(f"report_written=true report_name={report_path.name}")
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
