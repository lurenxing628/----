#!/usr/bin/env python3
"""Build reference diagnostics for optimizer comparison benchmarks."""

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

from tests._support.optimizer_reference_diagnostics import (  # noqa: E402
    DEFAULT_REFERENCE_DIAGNOSTICS_OUTPUT,
    build_reference_diagnostics,
    write_reference_diagnostics,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build optimizer benchmark reference diagnostics.")
    parser.add_argument("--objective", default="min_overdue", help="objective name to diagnose")
    parser.add_argument("--output", default=str(DEFAULT_REFERENCE_DIAGNOSTICS_OUTPUT), help="ignored output path")
    parser.add_argument("--no-write", action="store_true", help="print only; do not write ignored evidence")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    payload = build_reference_diagnostics(objective_name=str(args.objective))
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    if not args.no_write:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = REPO_ROOT / output_path
        write_reference_diagnostics(output_path, payload)
    return 0 if payload.get("status") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
