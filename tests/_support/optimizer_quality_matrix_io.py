"""Explicit diagnostic saving and clean-only baseline promotion."""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from tests._support.optimizer_quality_matrix_compare import compare_quality_matrices, finite_number, validate_snapshot
from tests._support.optimizer_quality_matrix_provenance import capture_source, machine_metadata

DIAGNOSTIC_DIR = Path("evidence/QualityGate/long_gate/optimizer_quality_matrix")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: " + key)
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite JSON number: " + value)


def read_snapshot(path):
    with Path(path).open(encoding="utf-8") as stream:
        return json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)


def _write_json(path, payload):
    text = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent), delete=False) as stream:
            name = stream.name
            stream.write(text)
        os.replace(name, str(path))
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def write_diagnostic(path, payload, repo_root):
    path = Path(path).resolve()
    root = Path(repo_root).resolve()
    if path.name.startswith("optimizer_quality_matrix"):
        raise ValueError("diagnostics cannot use the reserved optimizer_quality_matrix baseline filename prefix")
    if root in path.parents and (root / DIAGNOSTIC_DIR).resolve() not in path.parents:
        raise ValueError("in-repo diagnostics must stay under " + str(DIAGNOSTIC_DIR))
    _write_json(path, payload)


def update_baseline(snapshot, baseline_path, repo_root, runtime_ratio=3.0, runtime_slack_ms=250.0):
    finite_number(runtime_ratio, "runtime_ratio", 1.0)
    finite_number(runtime_slack_ms, "runtime_slack_ms")
    validate_snapshot(snapshot)
    if snapshot["proof_binding"] != "clean_matrix_run_not_full_quality_gate":
        raise ValueError("formal baseline requires a clean passed matrix run; dirty/changed evidence is diagnostic only")
    current = capture_source(repo_root)
    if not current["worktree_clean"] or current != snapshot["source_after"]:
        raise ValueError("formal baseline requires current clean source to match the measured HEAD and source receipt")
    if snapshot["machine"] != machine_metadata():
        raise ValueError("formal baseline machine/runtime mismatch")
    path = Path(baseline_path).resolve()
    if not path.name.startswith("optimizer_quality_matrix") or path.suffix != ".json":
        raise ValueError("use a new optimizer_quality_matrix*.json baseline; old baselines are not writable here")
    if path.exists():
        previous = read_snapshot(path)
        comparison = compare_quality_matrices(previous, snapshot, runtime_ratio, runtime_slack_ms)
        if comparison["status"] != "passed":
            raise ValueError("baseline update would bless a regression: " + "; ".join(comparison["failures"]))
    _write_json(path, snapshot)
