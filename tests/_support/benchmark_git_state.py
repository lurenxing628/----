from __future__ import annotations

import subprocess
from pathlib import Path


def git_commit(repo_root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return "unknown"
    if result.returncode != 0:
        return "unknown"
    text = str(result.stdout or "").strip()
    return text or "unknown"


def dirty_worktree(repo_root: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=str(repo_root),
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError:
        return True
    if result.returncode != 0:
        return True
    return bool(str(result.stdout or "").strip())


def proof_binding_status(*, dirty_worktree: bool) -> str:
    return "unbound_dirty_worktree" if bool(dirty_worktree) else "clean_worktree"


__all__ = ["dirty_worktree", "git_commit", "proof_binding_status"]
