"""Source receipts for the wall-clock algorithm comparison protocol."""
from __future__ import annotations

import hashlib
import os
import platform
import sqlite3
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

COMPARE_SCHEMA_VERSION = 2
MEASUREMENT = {
    "clock": "time.perf_counter",
    "scope": "baseline_and_all_search_and_production_repair",
    "budget_scope": "baseline_and_search",
    "execution": "serial_single_worker",
}
SOURCE_PATHS = (
    "core", "data", "schema.sql",
    "tests/_support/optimizer_compare_algorithms*.py",
    "tests/_support/optimizer_smtwt_compare*.py",
    "tests/_support/optimizer_graph_ready*.py",
    "tests/_support/optimizer_benchmark*.py",
    "tests/_support/optimizer_reference_diagnostics.py",
    "tests/_support/benchmark_parallel.py",
    "tests/_scripts_e2e/benchmark_optimizer_compare_algorithms.py",
    "tests/_scripts_e2e/benchmark_optimizer_smtwt_compare_algorithms.py",
    "tests/_scripts_e2e/benchmark_optimizer_graph_ready_v2_long_run.py",
    "tests/_scripts_e2e/benchmark_optimizer_long_run.py",
    "tests/_scripts_e2e/benchmark_optimizer_ratchet.py",
    "tests/_data/optimizer_benchmarks",
)


def capture_source(repo_root):
    root = Path(repo_root).resolve()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root)] + list(args))

    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all").decode("utf-8").split("\0")[:-1]
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", *SOURCE_PATHS).decode("utf-8").split("\0")
    digest = hashlib.sha256()
    for name in sorted(set(paths) - {""}):
        path = root / name
        if path.suffix == ".pyc" or "__pycache__" in path.parts:
            continue
        digest.update(name.encode("utf-8") + b"\0")
        digest.update(path.read_bytes() if path.is_file() else b"<deleted>")
        digest.update(b"\0")
    return {
        "repo_root": str(root), "head": git("rev-parse", "HEAD").decode().strip(),
        "branch": git("rev-parse", "--abbrev-ref", "HEAD").decode().strip(),
        "status_porcelain": status, "worktree_clean": not status,
        "diff_sha256": hashlib.sha256(git("diff", "--binary", "HEAD")).hexdigest(),
        "source_sha256": digest.hexdigest(),
    }


def machine_metadata():
    return {
        "node": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
        "cpu_count": os.cpu_count(), "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(), "python_executable": sys.executable,
        "sqlite_version": sqlite3.sqlite_version, "networkx_version": version("networkx"),
    }


def source_binding(before, after):
    if any(before[key] != after[key] for key in ("head", "source_sha256")):
        return "unbound_source_changed"
    if not before["worktree_clean"] or not after["worktree_clean"]:
        return "unbound_dirty_worktree"
    return "clean_worktree"


def require_serial_workers(workers):
    if type(workers) is not int or workers != 1:
        raise ValueError("wall-clock algorithm comparisons require --workers 1")
    return workers
