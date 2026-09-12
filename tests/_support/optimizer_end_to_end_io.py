"""End-to-end diagnostics and clean-source baseline promotion."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from tests._support.optimizer_quality_matrix_provenance import machine_metadata

DIAGNOSTIC_DIR = Path("evidence/QualityGate/long_gate/optimizer_end_to_end")
REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_PATHS = (
    "core", "data", "schema.sql", "tests/_support/optimizer_end_to_end*.py",
    "tests/_support/optimizer_exact_oracle.py", "tests/_support/optimizer_quality_matrix*.py",
    "tests/_scripts_e2e/benchmark_optimizer_end_to_end.py",
    "tests/algorithm/test_optimizer_end_to_end*.py",
    "tests/algorithm/test_optimizer_exact_oracle*.py",
)


def capture_end_to_end_source(repo_root):
    """Hash source bytes, including untracked helpers, independently of Git HEAD."""
    root = Path(repo_root).resolve()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root)] + list(args))

    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all").decode("utf-8").split("\0")[:-1]
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *SOURCE_PATHS)
    digest = hashlib.sha256()
    for name in sorted(set(paths.decode("utf-8").split("\0")) - {""}):
        if Path(name).suffix not in (".py", ".sql"):
            continue
        digest.update(name.encode("utf-8") + b"\0")
        path = root / name
        digest.update(path.read_bytes() if path.is_file() else b"<deleted>")
        digest.update(b"\0")
    return {
        "repo_root": str(root), "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
        "status_porcelain": status, "worktree_clean": not status,
        "diff_sha256": hashlib.sha256(git("diff", "--binary", "HEAD")).hexdigest(),
        "source_sha256": digest.hexdigest(),
    }


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
    """Read and validate before accepting a file as an end-to-end snapshot."""
    from tests._support.optimizer_end_to_end_compare import validate_snapshot

    with Path(path).open(encoding="utf-8") as stream:
        payload = json.load(stream, object_pairs_hook=_unique_object, parse_constant=_reject_constant)
    validate_snapshot(payload)
    return payload


def _write_json(path, payload):
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=str(path.parent), delete=False) as stream:
            name = stream.name
            stream.write(serialized)
        os.replace(name, str(path))
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)


def write_diagnostic(path, payload, repo_root):
    path = Path(path).resolve()
    root = Path(repo_root).resolve()
    if path.name.casefold().startswith(("optimizer_end_to_end", "optimizer_quality_matrix")):
        raise ValueError("diagnostics cannot use a reserved optimizer baseline filename prefix")
    for parent in path.parents:
        if parent.exists() and parent.samefile(root):
            relative = path.relative_to(parent)
            if relative.parts[:len(DIAGNOSTIC_DIR.parts)] != DIAGNOSTIC_DIR.parts:
                raise ValueError("in-repo diagnostics must stay under " + str(DIAGNOSTIC_DIR))
            break
    _write_json(path, payload)


def update_baseline(snapshot, baseline_path, repo_root, runtime_ratio=3.0, runtime_slack_ms=250.0):
    from tests._support.optimizer_end_to_end_cases import OBJECTIVES, SCENARIOS
    from tests._support.optimizer_end_to_end_compare import compare_end_to_end_matrices, validate_snapshot
    from tests._support.optimizer_quality_matrix_compare import finite_number

    finite_number(runtime_ratio, "runtime_ratio", 1.0)
    finite_number(runtime_slack_ms, "runtime_slack_ms")
    validate_snapshot(snapshot)
    if snapshot["config"]["decoder_count_mode"] != "native":
        raise ValueError("formal baseline requires native decoder counts; uncounted evidence is diagnostic only")
    if (set(snapshot["coverage"]["scenarios"]) != set(SCENARIOS)
            or set(snapshot["coverage"]["objectives"]) != set(OBJECTIVES)):
        raise ValueError("formal baseline requires every scenario and all four objectives")
    root = Path(repo_root).resolve()
    if root != REPO_ROOT or snapshot["source_after"]["repo_root"] != str(root):
        raise ValueError("formal baseline source root must match the executing checkout")
    if snapshot["proof_binding"] != "clean_matrix_run_not_full_quality_gate":
        raise ValueError("formal baseline requires a clean passed run; dirty/changed evidence is diagnostic only")
    current = capture_end_to_end_source(root)
    if not current["worktree_clean"] or current != snapshot["source_after"]:
        raise ValueError("formal baseline requires current clean source to match the measured HEAD and source receipt")
    if snapshot["machine"] != machine_metadata():
        raise ValueError("formal baseline machine/runtime mismatch")
    path = Path(baseline_path).resolve()
    if not path.name.startswith("optimizer_end_to_end") or path.suffix != ".json":
        raise ValueError("use an optimizer_end_to_end*.json baseline; old baselines are not writable here")
    if path.exists():
        comparison = compare_end_to_end_matrices(read_snapshot(path), snapshot, runtime_ratio, runtime_slack_ms)
        if comparison["status"] != "passed":
            raise ValueError("baseline update would bless a regression: " + "; ".join(comparison["failures"]))
    _write_json(path, snapshot)
