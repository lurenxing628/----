#!/usr/bin/env python3
"""Compare optimizer algorithm profiles on the same benchmark matrix."""

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

from tests._support.optimizer_compare_algorithms import (  # noqa: E402
    DEFAULT_ALGORITHM_PROFILES,
    build_algorithm_comparison,
    compare_to_algorithm_baseline,
)

DEFAULT_COMPARE_BASELINE = Path(".codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare optimizer algorithm profiles.")
    parser.add_argument("--profiles", default=",".join(DEFAULT_ALGORITHM_PROFILES), help="comma-separated algorithm profiles")
    parser.add_argument("--seeds", type=int, default=10, help="seed count")
    parser.add_argument("--baseline", default=str(DEFAULT_COMPARE_BASELINE), help="comparison baseline path")
    parser.add_argument("--update-baseline", action="store_true", help="write current comparison baseline")
    parser.add_argument("--check-baseline", action="store_true", help="compare current output with baseline")
    parser.add_argument(
        "--allow-dirty-proof",
        action="store_true",
        help="allow dirty-worktree comparison only as unbound proof, never as clean proof",
    )
    parser.add_argument("--no-write", action="store_true", help="print only; do not write ignored output")
    parser.add_argument("--output", default="evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_compare_algorithms.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    profiles = [item.strip() for item in str(args.profiles or "").split(",") if item.strip()]
    payload = build_algorithm_comparison(profiles=profiles, seeds=int(args.seeds))
    baseline_path = _repo_path(Path(args.baseline))
    result = {"comparison": payload}
    status = str(payload.get("status") or "failed")
    proof_status = _proof_check(payload, allow_dirty=bool(args.allow_dirty_proof))
    if proof_status:
        result["proof_check"] = proof_status

    if args.update_baseline:
        if payload.get("dirty_worktree") is True and not args.allow_dirty_proof:
            result["baseline_write"] = {
                "status": "failed",
                "reason": "dirty_actual_worktree",
                "proof_binding_status": "unbound_dirty_worktree",
            }
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
            return 1
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        baseline_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["baseline_written"] = _display_path(baseline_path)
    elif args.check_baseline:
        if not baseline_path.exists():
            result["baseline_check"] = {"status": "failed", "failure_count": 1, "failures": [{"reason": "missing_baseline"}]}
            status = "failed"
        else:
            baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
            result["baseline_check"] = compare_to_algorithm_baseline(
                payload,
                baseline,
                require_clean_proof=not args.allow_dirty_proof,
            )
            status = str(result["baseline_check"]["status"])

    if not args.no_write and not args.update_baseline:
        output_path = _repo_path(Path(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["output_written"] = _display_path(output_path)

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if proof_status and proof_status.get("status") != "passed":
        status = "failed"
    return 0 if status == "passed" else 1


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _proof_check(payload: dict, *, allow_dirty: bool) -> dict:
    if payload.get("dirty_worktree") is True and not allow_dirty:
        return {
            "status": "failed",
            "reason": "dirty_actual_worktree",
            "proof_binding_status": payload.get("proof_binding_status") or "unbound_dirty_worktree",
        }
    if payload.get("dirty_worktree") is True:
        return {
            "status": "passed",
            "proof_binding_status": payload.get("proof_binding_status") or "unbound_dirty_worktree",
            "require_clean_proof": False,
        }
    return {"status": "passed", "proof_binding_status": payload.get("proof_binding_status") or "clean_worktree"}


if __name__ == "__main__":
    raise SystemExit(main())
