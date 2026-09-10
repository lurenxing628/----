"""Local source receipts. Clean matrix evidence is not a full quality-gate proof."""
from __future__ import annotations

import hashlib
import os
import platform
import sqlite3
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path


def capture_source(repo_root):
    root = Path(repo_root).resolve()

    def git(*args):
        return subprocess.check_output(["git", "-C", str(root)] + list(args))

    status = git("status", "--porcelain=v1", "-z", "--untracked-files=all").decode("utf-8").split("\0")[:-1]
    paths = git("ls-files", "--cached", "--others", "--exclude-standard", "-z", "--", "core", "data", "schema.sql",
                "tests/_support/optimizer_quality_matrix*.py", "tests/_scripts_e2e/benchmark_optimizer_quality_matrix.py",
                "tests/algorithm/test_optimizer_quality_matrix_contract.py").decode("utf-8").split("\0")
    digest = hashlib.sha256()
    for name in sorted(set(paths) - {""}):
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


def machine_metadata():
    return {
        "node": platform.node(), "platform": platform.platform(), "machine": platform.machine(),
        "cpu_count": os.cpu_count(), "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(), "python_executable": sys.executable,
        "sqlite_version": sqlite3.sqlite_version, "networkx_version": version("networkx"),
    }


def proof_binding(before, after):
    if before != after:
        return "unbound_source_changed"
    if not before["worktree_clean"]:
        return "unbound_dirty_worktree"
    return "clean_matrix_run_not_full_quality_gate"
