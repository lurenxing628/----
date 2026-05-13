from __future__ import annotations

import fnmatch
import glob
import hashlib
import importlib.metadata
import json
import os
import platform
import stat
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from tools.long_gate_schema import LONG_GATE_FINGERPRINT_SCHEMA_VERSION, stable_json_hash

_EXPECTED_COLLECT_NODEIDS_SCHEMA_VERSION = 1


class LongGateFingerprintError(RuntimeError):
    pass


def _collect_nodeids_by_file(nodeids: Sequence[str]) -> Dict[str, List[str]]:
    grouped: Dict[str, List[str]] = {}
    for nodeid in nodeids:
        file_path = str(nodeid).split("::", 1)[0]
        grouped.setdefault(file_path, []).append(str(nodeid))
    return {path: grouped[path] for path in sorted(grouped)}


def _sha256_file(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _run_git_paths(repo_root: str, args: Sequence[str], *, strict: bool) -> List[str]:
    try:
        proc = subprocess.run(
            ["git", *list(args)],
            cwd=repo_root,
            capture_output=True,
            timeout=10,
        )
    except subprocess.TimeoutExpired as exc:
        if strict:
            raise LongGateFingerprintError(
                f"git command timed out while building long gate fingerprint: git {' '.join(args)}"
            ) from exc
        return []
    except OSError as exc:
        if strict:
            raise LongGateFingerprintError(
                f"git command failed while building long gate fingerprint: git {' '.join(args)}: {exc}"
            ) from exc
        return []
    if int(proc.returncode) != 0:
        if strict:
            stderr = bytes(proc.stderr or b"").decode("utf-8", errors="replace").strip()
            stdout = bytes(proc.stdout or b"").decode("utf-8", errors="replace").strip()
            detail = stderr or stdout or f"returncode={proc.returncode}"
            raise LongGateFingerprintError(
                f"git command failed while building long gate fingerprint: git {' '.join(args)}: {detail}"
            )
        return []
    return [
        raw.decode("utf-8", errors="replace").replace("\\", "/")
        for raw in bytes(proc.stdout or b"").split(b"\0")
        if raw
    ]


def _git_path_sources(repo_root: str, *, strict: bool) -> Tuple[Set[str], Set[str], str]:
    try:
        tracked = set(_run_git_paths(repo_root, ["ls-files", "-z"], strict=True))
        untracked = set(
            _run_git_paths(
                repo_root,
                ["ls-files", "--others", "--exclude-standard", "-z"],
                strict=True,
            )
        )
    except LongGateFingerprintError:
        if strict:
            raise
        return set(), set(), "unavailable"
    return tracked, untracked, "available"


def _has_glob_chars(value: str) -> bool:
    return any(char in value for char in "*?[")


def _normalize_scope_path(path: str) -> str:
    normalized = str(path or "").replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _real_repo_root(repo_root: str) -> str:
    return os.path.realpath(os.path.abspath(repo_root))


def _is_within_repo(abs_path: str, repo_root: str) -> bool:
    root = _real_repo_root(repo_root)
    real_path = os.path.realpath(abs_path)
    return real_path == root or real_path.startswith(root + os.sep)


def _abs_for_scope_path(path: str, repo_root: str) -> str:
    normalized = _normalize_scope_path(path)
    if os.path.isabs(normalized):
        return normalized
    return os.path.join(_real_repo_root(repo_root), normalized.replace("/", os.sep))


def _candidate_paths_for_scope(scope: str, repo_root: str, tracked: Set[str], untracked: Set[str]) -> Set[str]:
    normalized_scope = _normalize_scope_path(scope)
    if not normalized_scope:
        return set()
    if not _has_glob_chars(normalized_scope):
        return {normalized_scope}

    candidates = {
        path
        for path in set(tracked) | set(untracked)
        if fnmatch.fnmatch(path, normalized_scope)
    }
    root = _real_repo_root(repo_root)
    glob_pattern = normalized_scope if os.path.isabs(normalized_scope) else os.path.join(root, normalized_scope)
    if not _is_within_repo(glob_pattern, root):
        candidates.add(normalized_scope)
    filesystem_matches = glob.glob(glob_pattern, recursive=True)
    for abs_path in filesystem_matches:
        if os.path.isfile(abs_path) or os.path.isdir(abs_path) or os.path.islink(abs_path):
            candidates.add(os.path.relpath(abs_path, root).replace("\\", "/"))
    return candidates


def _file_mode(path: str, kind: str) -> str:
    try:
        mode = os.lstat(path).st_mode
    except OSError:
        return ""
    if kind == "file":
        return f"100{stat.S_IMODE(mode):03o}"
    if kind == "directory":
        return f"040{stat.S_IMODE(mode):03o}"
    if kind == "symlink":
        return f"120{stat.S_IMODE(mode):03o}"
    return f"{stat.S_IMODE(mode):06o}"


def _fingerprint_one_file(rel_path: str, repo_root: str, tracked: Set[str], untracked: Set[str]) -> Dict[str, Any]:
    normalized = _normalize_scope_path(rel_path)
    abs_path = _abs_for_scope_path(normalized, repo_root)
    if not os.path.islink(abs_path) and not _is_within_repo(abs_path, repo_root):
        return {
            "path": normalized,
            "exists": False,
            "kind": "outside_repo",
            "size": 0,
            "mode": "",
            "sha256": "",
            "source": "outside_repo",
        }
    exists = os.path.lexists(abs_path)
    if normalized in tracked:
        source = "tracked"
    elif normalized in untracked:
        source = "untracked"
    elif exists:
        source = "filesystem"
    else:
        source = "missing"

    if not exists:
        return {
            "path": normalized,
            "exists": False,
            "kind": "missing",
            "size": 0,
            "mode": "",
            "sha256": "",
            "source": source,
        }

    if os.path.islink(abs_path):
        kind = "symlink"
        try:
            link_target = os.readlink(abs_path)
        except OSError:
            link_target = ""
        link_realpath = os.path.realpath(abs_path)
        if not _is_within_repo(link_realpath, repo_root):
            kind = "symlink_outside_repo"
        digest = hashlib.sha256(link_target.encode("utf-8", errors="replace")).hexdigest()
        size = len(link_target.encode("utf-8", errors="replace"))
    elif os.path.isfile(abs_path):
        kind = "file"
        digest = _sha256_file(abs_path)
        size = os.path.getsize(abs_path)
    elif os.path.isdir(abs_path):
        kind = "directory"
        digest = ""
        size = 0
    else:
        kind = "other"
        digest = ""
        size = 0

    return {
        "path": normalized,
        "exists": True,
        "kind": kind,
        "size": int(size),
        "mode": _file_mode(abs_path, kind),
        "sha256": digest,
        "source": source,
    }


def fingerprint_files(paths_or_patterns: Sequence[str], repo_root: str, *, strict: bool = False) -> Dict[str, Any]:
    root = os.path.abspath(repo_root)
    tracked, untracked, git_source_status = _git_path_sources(root, strict=strict)
    rel_paths: Set[str] = set()
    for scope in list(paths_or_patterns or []):
        rel_paths.update(_candidate_paths_for_scope(str(scope), root, tracked, untracked))

    files = [_fingerprint_one_file(path, root, tracked, untracked) for path in sorted(rel_paths)]
    path_rows = [
        {
            "path": row["path"],
            "exists": row["exists"],
            "kind": row["kind"],
            "source": row["source"],
        }
        for row in files
    ]
    return {
        "git_source_status": git_source_status,
        "paths_hash": stable_json_hash(path_rows),
        "content_hash": stable_json_hash(files),
        "files": files,
    }


def fingerprint_command(command: Mapping[str, Any]) -> str:
    normalized = {
        "display": str(command.get("display") or "").strip(),
        "args": [str(arg) for arg in list(command.get("args") or [])],
        "capture_output": bool(command.get("capture_output")),
        "output_policy": str(command.get("output_policy") or "exact").strip().lower(),
    }
    return stable_json_hash(normalized)


def _pytest_version(*, strict: bool = False) -> str:
    try:
        return importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError as exc:
        if strict:
            raise LongGateFingerprintError("pytest distribution is required for long gate fingerprint") from exc
        return "__missing_pytest_distribution__"


def pytest_distribution_version(*, strict: bool = False) -> str:
    return _pytest_version(strict=strict)


def _runtime_fingerprint_value(key: str, *, strict: bool = False) -> Optional[str]:
    if key == "python_executable_realpath":
        return os.path.realpath(sys.executable)
    if key == "python_version":
        return sys.version.splitlines()[0].strip()
    if key == "pytest_version":
        return _pytest_version(strict=strict)
    if key == "platform":
        return platform.platform()
    return os.environ.get(str(key))


def fingerprint_environment(keys: Sequence[str], *, strict: bool = False) -> Dict[str, Any]:
    values = {str(key): _runtime_fingerprint_value(str(key), strict=strict) for key in list(keys or [])}
    return {
        "keys": [str(key) for key in list(keys or [])],
        "values": values,
        "hash": stable_json_hash(values),
    }


def _entry_file_scopes(entry: Mapping[str, Any]) -> List[str]:
    scopes: List[str] = []
    for key in ("input_file_scopes", "config_file_scopes", "tool_file_scopes", "dependency_file_scopes"):
        scopes.extend(str(item) for item in list(entry.get(key) or []))
    return list(dict.fromkeys(scopes))


def _entry_output_result_files(entry: Mapping[str, Any]) -> List[str]:
    return list(dict.fromkeys(str(item).replace("\\", "/") for item in list(entry.get("output_result_files") or [])))


def _collect_nodeids_component(repo_root: str) -> Dict[str, Any]:
    rel_path = "evidence/QualityGate/collect_nodeids.json"
    abs_path = _abs_for_scope_path(rel_path, repo_root)
    component: Dict[str, Any] = {
        "path": rel_path,
        "exists": os.path.isfile(abs_path),
        "validated": False,
        "schema_version": None,
        "status": "",
        "nodeid_hash": "",
        "nodeid_count": None,
        "error": "",
    }
    if not component["exists"]:
        return component
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        component["error"] = str(exc)
        return component
    if not isinstance(payload, dict):
        component["error"] = "collect_nodeids payload must be an object"
        return component
    raw_nodeids = payload.get("nodeids")
    nodeids = [str(item) for item in raw_nodeids] if isinstance(raw_nodeids, list) else []
    expected_nodeids_by_file = _collect_nodeids_by_file(nodeids)
    component["schema_version"] = payload.get("schema_version")
    component["status"] = str(payload.get("status") or "")
    component["nodeid_hash"] = str(payload.get("nodeid_hash") or "")
    component["nodeid_count"] = payload.get("nodeid_count")
    if component["schema_version"] != _EXPECTED_COLLECT_NODEIDS_SCHEMA_VERSION:
        component["error"] = "collect_nodeids schema_version is invalid"
    elif not isinstance(raw_nodeids, list) or any(not isinstance(item, str) for item in raw_nodeids):
        component["error"] = "collect_nodeids nodeids must be a list of strings"
    elif component["nodeid_count"] != len(nodeids):
        component["error"] = "collect_nodeids nodeid_count does not match nodeids"
    elif not component["nodeid_hash"]:
        component["error"] = "collect_nodeids nodeid_hash is missing"
    elif component["nodeid_hash"] != stable_json_hash(nodeids):
        component["error"] = "collect_nodeids nodeid_hash does not match nodeids"
    elif payload.get("nodeids_by_file") != expected_nodeids_by_file:
        component["error"] = "collect_nodeids nodeids_by_file does not match nodeids"
    else:
        component["validated"] = True
    return component


def fingerprint_entry(entry: Mapping[str, Any], repo_root: str, *, strict: bool = False) -> Dict[str, Any]:
    command_payload = {
        "display": entry.get("display"),
        "args": entry.get("args"),
        "capture_output": entry.get("capture_output"),
        "output_policy": entry.get("output_policy"),
    }
    env_keys = [str(key) for key in list(entry.get("env_keys") or [])]
    components = {
        "command_hash": fingerprint_command(command_payload),
        "files": fingerprint_files(_entry_file_scopes(entry), repo_root, strict=strict),
        "environment": fingerprint_environment(env_keys, strict=strict),
        "output_result_files": {
            "paths": _entry_output_result_files(entry),
            "hash": stable_json_hash(_entry_output_result_files(entry)),
        },
    }
    if str(entry.get("entry_id") or "") == "full_test_debt":
        components["collect_nodeids"] = _collect_nodeids_component(repo_root)
    payload = {
        "schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "components": components,
    }
    payload["hash"] = f"sha256:{stable_json_hash(payload)}"
    return payload


def _files_by_path(fingerprint: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    components = fingerprint.get("components") if isinstance(fingerprint.get("components"), dict) else {}
    files_component = components.get("files") if isinstance(components, dict) else {}
    files = files_component.get("files") if isinstance(files_component, dict) else []
    return {str(row.get("path") or ""): row for row in list(files or []) if isinstance(row, dict)}


def diff_fingerprints(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    reasons: List[str] = []
    if previous.get("schema_version") != current.get("schema_version"):
        reasons.append("fingerprint schema changed")
    if previous.get("hash") == current.get("hash") and not reasons:
        return {"changed": False, "reasons": []}

    previous_files = _files_by_path(previous)
    current_files = _files_by_path(current)
    for path in sorted(set(current_files) - set(previous_files)):
        reasons.append(f"added input file: {path}")
    for path in sorted(set(previous_files) - set(current_files)):
        reasons.append(f"removed input file: {path}")
    for path in sorted(set(previous_files) & set(current_files)):
        before = previous_files[path]
        after = current_files[path]
        if before.get("sha256") != after.get("sha256") or before.get("exists") != after.get("exists"):
            reasons.append(f"modified input file: {path}")

    if not reasons:
        reasons.append("input fingerprint changed")
    return {"changed": True, "reasons": reasons}
