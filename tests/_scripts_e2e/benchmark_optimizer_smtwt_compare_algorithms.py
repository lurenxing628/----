#!/usr/bin/env python3
"""Compare optimizer algorithm profiles on all SMTWT overdue benchmark instances."""

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

from tests._support.optimizer_smtwt_compare_algorithms import (  # noqa: E402
    DEFAULT_SMTWT_PROFILES,
    build_smtwt_algorithm_comparison,
)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare optimizer algorithms on SMTWT overdue benchmark instances.")
    parser.add_argument("--profiles", default=",".join(DEFAULT_SMTWT_PROFILES), help="comma-separated algorithm profiles")
    parser.add_argument("--sizes", default="40,50", help="comma-separated SMTWT sizes")
    parser.add_argument("--seeds", type=int, default=1, help="seed count")
    parser.add_argument("--limit-per-size", type=int, default=None, help="optional debug limit per size")
    parser.add_argument("--time-budget", type=int, default=1, help="time budget seconds for improve algorithms")
    parser.add_argument("--workers", type=int, default=10, help="parallel worker process count")
    parser.add_argument(
        "--allow-dirty-proof",
        action="store_true",
        help="allow dirty-worktree comparison only as unbound proof, never as clean proof",
    )
    parser.add_argument("--no-write", action="store_true", help="print only")
    parser.add_argument("--summary-only", action="store_true", help="print summary and pairwise tables without row details")
    parser.add_argument("--output", default="evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_smtwt_compare_algorithms.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(list(argv) if argv is not None else None)
    profiles = [item.strip() for item in str(args.profiles or "").split(",") if item.strip()]
    sizes = [int(item.strip()) for item in str(args.sizes or "").split(",") if item.strip()]
    payload = build_smtwt_algorithm_comparison(
        profiles=profiles,
        sizes=sizes,
        seeds=int(args.seeds),
        limit_per_size=args.limit_per_size,
        time_budget_seconds=int(args.time_budget),
        workers=int(args.workers),
    )
    result = {"comparison": _printable_payload(payload, summary_only=bool(args.summary_only))}
    proof_status = _proof_check(payload, allow_dirty=bool(args.allow_dirty_proof))
    if proof_status:
        result["proof_check"] = proof_status
    if not args.no_write:
        output_path = _repo_path(Path(args.output))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        result["output_written"] = _display_path(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    status = "passed" if payload.get("status") == "passed" and (not proof_status or proof_status.get("status") == "passed") else "failed"
    return 0 if status == "passed" else 1


def _repo_path(path: Path) -> Path:
    return path if path.is_absolute() else REPO_ROOT / path


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _printable_payload(payload: dict, *, summary_only: bool) -> dict:
    if not summary_only:
        return payload
    out = dict(payload)
    out["rows"] = {"omitted": True, "row_count": len(payload.get("rows") or [])}
    return out


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
