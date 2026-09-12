#!/usr/bin/env python3
"""Compare optimizer algorithm profiles on the same benchmark matrix."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
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
from tests._support.optimizer_compare_algorithms_provenance import (  # noqa: E402
    COMPARE_SCHEMA_VERSION,
    capture_source,
    machine_metadata,
    source_binding,
)

DEFAULT_COMPARE_BASELINE = Path(".codestable/roadmap/scheduler-global-optimizer/graph-ready-v2-comparison-baseline.json")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compare optimizer algorithm profiles.")
    parser.add_argument("--profiles", default=",".join(DEFAULT_ALGORITHM_PROFILES), help="comma-separated algorithm profiles")
    parser.add_argument("--seeds", type=int, default=10, help="seed count")
    parser.add_argument("--workers", type=int, choices=(1,), default=1, help="one worker preserves wall-clock comparability")
    parser.add_argument("--baseline", default=str(DEFAULT_COMPARE_BASELINE), help="comparison baseline path")
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--update-baseline", action="store_true", help="write a passed, clean comparison baseline")
    action.add_argument("--check-baseline", action="store_true", help="compare current output with baseline")
    parser.add_argument(
        "--allow-dirty-proof",
        action="store_true",
        help="allow dirty-worktree comparison only as unbound proof, never as clean proof",
    )
    parser.add_argument("--no-write", action="store_true", help="print only; do not write ignored output")
    parser.add_argument("--output", default="evidence/QualityGate/long_gate/optimizer_benchmark/optimizer_compare_algorithms.json")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.update_baseline and args.allow_dirty_proof:
        parser.error("--allow-dirty-proof is diagnostic only and cannot be used with --update-baseline")
    baseline_path = _repo_path(Path(args.baseline))
    if args.update_baseline or args.check_baseline:
        preflight = _preflight_baseline(baseline_path, allow_dirty=args.allow_dirty_proof, updating=args.update_baseline)
        if preflight is not None:
            print(json.dumps({"baseline_write" if args.update_baseline else "baseline_check": preflight}, ensure_ascii=False, sort_keys=True))
            return 1
    profiles = [item.strip() for item in str(args.profiles or "").split(",") if item.strip()]
    payload = build_algorithm_comparison(profiles=profiles, seeds=int(args.seeds), workers=args.workers)
    result = {"comparison": payload}
    status = str(payload.get("status") or "failed")
    proof_status = _proof_check(payload, allow_dirty=bool(args.allow_dirty_proof))
    if proof_status:
        result["proof_check"] = proof_status

    if args.update_baseline:
        result["baseline_write"] = _write_baseline(payload, baseline_path=baseline_path, allow_dirty=False)
        if result["baseline_write"]["status"] != "passed":
            status = "failed"
    elif args.check_baseline:
        result["baseline_check"] = _check_baseline(payload, baseline_path=baseline_path, allow_dirty=args.allow_dirty_proof)
        if result["baseline_check"]["status"] != "passed":
            status = "failed"

    if not args.no_write and not args.update_baseline:
        output_path = _repo_path(Path(args.output))
        result["diagnostic_write"] = _write_diagnostic(payload, output_path=output_path, baseline_path=baseline_path)
        if result["diagnostic_write"]["status"] != "passed":
            status = "failed"

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
    return _snapshot_check(payload, label="actual", allow_dirty=allow_dirty)

def _failure(reason: str, **details) -> dict:
    return {"status": "failed", "reason": reason, "failure_count": 1, "failures": [{"reason": reason, **details}]}


def _comparison_payload(payload: dict) -> dict:
    comparison = payload.get("comparison")
    return comparison if isinstance(comparison, dict) else payload


def _snapshot_check(payload: dict, *, label: str, allow_dirty: bool) -> dict:
    comparison = _comparison_payload(payload)
    if any(item.get("schema_version") != COMPARE_SCHEMA_VERSION or not isinstance(item.get("source_before"), dict)
           or not isinstance(item.get("source_after"), dict) for item in (payload, comparison)):
        return _failure(label + "_migration_required", detail="legacy timing/source evidence needs a new measured baseline")
    for key in ("schema_version", "status", "source_before", "source_after", "machine", "measurement",
                "git_commit", "dirty_worktree", "proof_binding_status"):
        if payload.get(key) != comparison.get(key):
            return _failure(label + "_comparison_metadata_mismatch", field=key)
    before, after = comparison["source_before"], comparison["source_after"]
    required = {"repo_root", "head", "branch", "status_porcelain", "worktree_clean", "diff_sha256", "source_sha256"}
    if not all(required.issubset(source) for source in (before, after)):
        return _failure(label + "_source_receipt_mismatch")
    for source in (before, after):
        if not isinstance(source["status_porcelain"], list) or not isinstance(source["worktree_clean"], bool):
            return _failure(label + "_invalid_source_receipt")
        if source["worktree_clean"] != (not source["status_porcelain"]):
            return _failure(label + "_invalid_source_receipt")
        for key, length in (("head", 40), ("source_sha256", 64), ("diff_sha256", 64)):
            value = source[key]
            if not isinstance(value, str) or len(value) != length or any(c not in "0123456789abcdef" for c in value):
                return _failure(label + "_invalid_source_receipt", field=key)
    binding = source_binding(before, after)
    if binding == "unbound_source_changed" or (not allow_dirty and before != after):
        return _failure(label + "_source_receipt_mismatch")
    dirty = not before["worktree_clean"] or not after["worktree_clean"]
    if comparison.get("git_commit") != after["head"] or comparison.get("dirty_worktree") is not dirty:
        return _failure(label + "_source_metadata_mismatch")
    if comparison.get("proof_binding_status") != binding:
        return _failure(label + "_source_metadata_mismatch")
    if not allow_dirty and dirty:
        return _failure("dirty_" + label + "_worktree")
    if payload.get("status") != "passed":
        return _failure(label + "_payload_failed")
    return compare_to_algorithm_baseline(comparison, comparison, require_clean_proof=not allow_dirty)


def _read_baseline(path: Path) -> dict:
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result

    def reject_constant(value):
        raise ValueError("nonfinite JSON number: " + value)

    payload = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object, parse_constant=reject_constant)
    if not isinstance(payload, dict):
        raise ValueError("baseline must be an object")
    return payload


def _check_baseline(payload: dict, *, baseline_path: Path, allow_dirty: bool) -> dict:
    if not baseline_path.exists():
        return _failure("missing_baseline")
    try:
        baseline = _read_baseline(baseline_path)
    except (OSError, ValueError) as exc:
        return _failure("invalid_baseline", detail=str(exc))
    for snapshot, label in ((baseline, "baseline"), (payload, "actual")):
        checked = _snapshot_check(snapshot, label=label, allow_dirty=allow_dirty)
        if checked["status"] != "passed":
            return checked
    return compare_to_algorithm_baseline(_comparison_payload(payload), _comparison_payload(baseline),
                                         require_clean_proof=not allow_dirty)


def _preflight_baseline(path: Path, *, allow_dirty: bool, updating: bool):
    """Reject an unusable reference before spending any search budget."""
    if not path.exists():
        return None if updating else _failure("missing_baseline")
    try:
        baseline = _read_baseline(path)
    except (OSError, ValueError) as exc:
        return _failure("invalid_baseline", detail=str(exc))
    checked = _snapshot_check(baseline, label="baseline", allow_dirty=allow_dirty)
    return checked if checked["status"] != "passed" else None


def _atomic_write(path: Path, payload: dict) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent), delete=False) as stream:
            temporary = stream.name
            stream.write(text)
        os.replace(temporary, str(path))
    finally:
        if temporary is not None and os.path.exists(temporary):
            os.unlink(temporary)


def _write_baseline(payload: dict, *, baseline_path: Path, allow_dirty: bool) -> dict:
    if allow_dirty:
        return _failure("dirty_proof_is_diagnostic_only")
    checked = _snapshot_check(payload, label="actual", allow_dirty=False)
    if checked["status"] != "passed":
        return checked
    if baseline_path.exists():
        checked = _check_baseline(payload, baseline_path=baseline_path, allow_dirty=False)
        if checked["status"] != "passed":
            return checked
    try:
        current = capture_source(REPO_ROOT)
        if current.get("worktree_clean") is not True or current != payload["source_after"]:
            return _failure("current_source_mismatch")
        if payload.get("machine") != machine_metadata():
            return _failure("current_machine_mismatch")
        _atomic_write(baseline_path, payload)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        return _failure("baseline_write_failed", detail=str(exc))
    return {"status": "passed", "path": _display_path(baseline_path), "proof_binding_status": payload["proof_binding_status"]}


def _write_diagnostic(payload: dict, *, output_path: Path, baseline_path: Path) -> dict:
    output = output_path.resolve()
    formal_dir = (REPO_ROOT / DEFAULT_COMPARE_BASELINE.parent).resolve()
    if output == baseline_path.resolve() or formal_dir in output.parents:
        return _failure("diagnostic_output_is_baseline_path")
    try:
        _atomic_write(output, payload)
    except (OSError, ValueError) as exc:
        return _failure("diagnostic_write_failed", detail=str(exc))
    return {"status": "passed", "path": _display_path(output)}


if __name__ == "__main__":
    raise SystemExit(main())
