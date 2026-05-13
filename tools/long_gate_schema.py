from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Mapping, Sequence

from tools.long_gate_paths import LONG_GATE_CACHE_DIR_REL, real_repo_root
from tools.quality_gate_shared import repo_identity

LONG_GATE_CACHE_SCHEMA_VERSION = 1
LONG_GATE_FINGERPRINT_SCHEMA_VERSION = 1
FULL_TEST_DEBT_NODE_CACHE_SCHEMA_VERSION = 1
LONG_GATE_MANIFEST_SCHEMA_VERSION = 1
LONG_GATE_SUMMARY_SCHEMA_VERSION = 1

LONG_GATE_RUNNER_VERSION_PATHS = ("scripts/run_quality_gate.py",)
LONG_GATE_TOOLING_VERSION_PATHS = (
    "tools/long_gate_cache.py",
    "tools/long_gate_collect.py",
    "tools/long_gate_fingerprint.py",
    "tools/long_gate_full_test_debt.py",
    "tools/long_gate_manifest.py",
    "tools/long_gate_paths.py",
    "tools/long_gate_schema.py",
    "tools/long_gate_summary.py",
)


def stable_json_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha256_file(abs_path: str) -> str:
    hasher = hashlib.sha256()
    with open(abs_path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _path_version_row(repo_root: str, rel_path: str) -> Dict[str, Any]:
    root = real_repo_root(repo_root)
    normalized = str(rel_path or "").replace("\\", "/")
    abs_path = (
        os.path.realpath(normalized)
        if os.path.isabs(normalized)
        else os.path.join(root, normalized.replace("/", os.sep))
    )
    abs_path = os.path.realpath(abs_path)
    target_inside_repo = abs_path == root or abs_path.startswith(root + os.sep)
    if not target_inside_repo:
        return {
            "path": normalized,
            "exists": os.path.lexists(abs_path),
            "kind": "outside_repo",
            "sha256": "",
            "target_inside_repo": False,
        }
    exists = os.path.lexists(abs_path)
    if not exists:
        return {"path": normalized, "exists": False, "kind": "missing", "sha256": ""}
    if os.path.islink(abs_path):
        try:
            target = os.readlink(abs_path)
        except OSError:
            target = ""
        target_realpath = os.path.realpath(abs_path)
        target_inside_repo = target_realpath == root or target_realpath.startswith(root + os.sep)
        target_content_sha256 = _sha256_file(target_realpath) if target_inside_repo and os.path.isfile(target_realpath) else ""
        return {
            "path": normalized,
            "exists": True,
            "kind": "symlink",
            "target_sha256": hashlib.sha256(target.encode("utf-8", errors="replace")).hexdigest(),
            "target_content_sha256": target_content_sha256,
            "target_realpath": target_realpath,
            "target_inside_repo": target_inside_repo,
        }
    if os.path.isfile(abs_path):
        return {"path": normalized, "exists": True, "kind": "file", "sha256": _sha256_file(abs_path)}
    if os.path.isdir(abs_path):
        return {"path": normalized, "exists": True, "kind": "directory", "sha256": ""}
    return {"path": normalized, "exists": True, "kind": "other", "sha256": ""}


def version_rows_for_paths(repo_root: str, rel_paths: Sequence[str]) -> List[Dict[str, Any]]:
    return [_path_version_row(repo_root, str(path)) for path in list(rel_paths or [])]


def _untrusted_paths_from_version_rows(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    untrusted: List[str] = []
    for row in rows:
        kind = str(row.get("kind") or "")
        if kind == "outside_repo" or (kind == "symlink" and not bool(row.get("target_inside_repo"))):
            untrusted.append(str(row.get("path") or ""))
    return untrusted


def version_hash_for_paths(repo_root: str, rel_paths: Sequence[str]) -> str:
    rows = version_rows_for_paths(repo_root, rel_paths)
    return f"sha256:{stable_json_hash(rows)}"


def version_untrusted_paths_for_paths(repo_root: str, rel_paths: Sequence[str]) -> List[str]:
    return _untrusted_paths_from_version_rows(version_rows_for_paths(repo_root, rel_paths))


def version_info_for_paths(repo_root: str, rel_paths: Sequence[str]) -> Dict[str, Any]:
    rows = version_rows_for_paths(repo_root, rel_paths)
    return {
        "hash": f"sha256:{stable_json_hash(rows)}",
        "untrusted_paths": _untrusted_paths_from_version_rows(rows),
    }


def long_gate_runner_version_hash(repo_root: str) -> str:
    return version_hash_for_paths(repo_root, LONG_GATE_RUNNER_VERSION_PATHS)


def long_gate_tooling_version_hash(repo_root: str) -> str:
    return version_hash_for_paths(repo_root, LONG_GATE_TOOLING_VERSION_PATHS)


def long_gate_repo_identity(repo_root: str) -> Dict[str, str]:
    identity = repo_identity(repo_root)
    return {
        "repo_root_realpath": os.path.realpath(str(identity.get("checkout_root_realpath") or repo_root)),
        "git_common_dir_realpath": os.path.realpath(
            str(identity.get("git_common_dir_realpath") or os.path.join(repo_root, ".git"))
        ),
    }


def long_gate_cache_metadata(repo_root: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> Dict[str, Any]:
    root = real_repo_root(repo_root)
    runner_version_info = version_info_for_paths(root, LONG_GATE_RUNNER_VERSION_PATHS)
    tooling_version_info = version_info_for_paths(root, LONG_GATE_TOOLING_VERSION_PATHS)
    metadata: Dict[str, Any] = {
        "cache_schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        "fingerprint_schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "runner_version_hash": str(runner_version_info["hash"]),
        "tooling_version_hash": str(tooling_version_info["hash"]),
        "runner_version_untrusted_paths": list(runner_version_info["untrusted_paths"]),
        "tooling_version_untrusted_paths": list(tooling_version_info["untrusted_paths"]),
        "cache_dir": str(cache_dir or LONG_GATE_CACHE_DIR_REL).replace("\\", "/"),
    }
    metadata.update(long_gate_repo_identity(root))
    return metadata
