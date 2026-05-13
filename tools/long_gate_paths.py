from __future__ import annotations

import os

LONG_GATE_CACHE_DIR_REL = os.path.join("evidence", "QualityGate", "long_gate").replace("\\", "/")
LONG_GATE_RESULTS_DIR_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "results").replace("\\", "/")
LONG_GATE_LOGS_DIR_REL = os.path.join(LONG_GATE_CACHE_DIR_REL, "logs").replace("\\", "/")
LONG_GATE_RESULTS_DIR_NAME = "results"
LONG_GATE_LOGS_DIR_NAME = "logs"


def normalize_repo_rel_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def real_repo_root(repo_root: str) -> str:
    return os.path.realpath(os.path.abspath(repo_root))


def is_within_repo(abs_path: str, repo_root: str) -> bool:
    root = real_repo_root(repo_root)
    real_path = os.path.realpath(os.path.abspath(abs_path))
    return real_path == root or real_path.startswith(root + os.sep)


def resolve_repo_path(repo_root: str, path: str, *, description: str = "cache path") -> str:
    root = real_repo_root(repo_root)
    raw_path = str(path or "").replace("\\", "/")
    if not raw_path:
        raise ValueError(f"{description} is empty")
    if os.path.isabs(raw_path):
        abs_path = os.path.realpath(raw_path)
    else:
        abs_path = os.path.realpath(os.path.join(root, raw_path.replace("/", os.sep)))
    if abs_path != root and not abs_path.startswith(root + os.sep):
        raise ValueError(f"{description} escapes repo root: {raw_path}")
    return abs_path


def repo_relative_path(repo_root: str, path: str, *, description: str = "cache path") -> str:
    root = real_repo_root(repo_root)
    raw_path = str(path or "").replace("\\", "/")
    if os.path.isabs(raw_path):
        abs_path = resolve_repo_path(root, raw_path, description=description)
        return os.path.relpath(abs_path, root).replace("\\", "/")
    resolve_repo_path(root, raw_path, description=description)
    return normalize_repo_rel_path(raw_path)
