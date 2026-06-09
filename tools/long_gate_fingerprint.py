from __future__ import annotations

import fnmatch
import glob
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import urllib.request
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, cast

from tools import architecture_scan_cache
from tools.long_gate_schema import LONG_GATE_FINGERPRINT_SCHEMA_VERSION, stable_json_hash

_EXPECTED_COLLECT_NODEIDS_SCHEMA_VERSION = 1
_RUNTIME_FINGERPRINT_CACHE: Dict[str, str] = {}


class LongGateFingerprintError(RuntimeError):
    def __init__(self, message: str, *, details: Optional[Mapping[str, Any]] = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


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
        "env_overlay": _normalize_env_overlay(command.get("env_overlay")),
    }
    return stable_json_hash(normalized)


def _normalize_env_overlay(value: Any) -> Dict[str, str]:
    if not isinstance(value, dict):
        return {}
    normalized: Dict[str, str] = {}
    for key in sorted(value):
        key_text = str(key or "").strip()
        if not key_text:
            continue
        normalized[key_text] = str(value.get(key) or "")
    return normalized


def _pytest_version(*, strict: bool = False) -> str:
    try:
        return importlib.metadata.version("pytest")
    except importlib.metadata.PackageNotFoundError as exc:
        if strict:
            raise LongGateFingerprintError("pytest distribution is required for long gate fingerprint") from exc
        return "__missing_pytest_distribution__"


def pytest_distribution_version(*, strict: bool = False) -> str:
    return _pytest_version(strict=strict)


def _distribution_version(distribution: str, *, strict: bool = False) -> str:
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError as exc:
        if strict:
            raise LongGateFingerprintError(
                f"{distribution} distribution is required for long gate fingerprint"
            ) from exc
        return "__missing_" + str(distribution).replace("-", "_") + "_distribution__"


def _effective_environment(environment: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    return environment if environment is not None else os.environ


def _runtime_probe_cache_key(probe: str, exe_realpath: str, environment: Mapping[str, str]) -> str:
    """探针成功值的去重键：(探针名, 解析出的可执行 realpath, 完整 env 签名)。

    同机同进程内同一 realpath + 同一 env 必产出逐位一致的 --version/capability，
    故缓存命中对指纹 proof 透明；env 任何差异（如 PATH overlay）即换键真跑，
    覆盖不弱。仅缓存成功值，strict/失败路径不入缓存（见各探针）。
    """
    return stable_json_hash({"probe": probe, "exe": exe_realpath, "env": dict(environment)})


def _git_executable_realpath(environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    git = shutil.which("git", path=env.get("PATH"))
    if not git:
        return "__missing_git__"
    return os.path.realpath(git)


def _git_version(*, strict: bool = False, environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    git = shutil.which("git", path=env.get("PATH"))
    if not git:
        return "__missing_git__"
    cache_key = _runtime_probe_cache_key("git_version", os.path.realpath(git), env)
    cached = _RUNTIME_FINGERPRINT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            [git, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=dict(env),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if strict:
            raise LongGateFingerprintError(f"git version is required for long gate fingerprint: {exc}") from exc
        return "__git_version_unavailable__"
    if int(completed.returncode) != 0:
        if strict:
            detail = str(completed.stderr or completed.stdout or "").strip() or f"returncode={completed.returncode}"
            raise LongGateFingerprintError(f"git version is required for long gate fingerprint: {detail}")
        return "__git_version_unavailable__"
    value = str(completed.stdout or "").strip()
    _RUNTIME_FINGERPRINT_CACHE[cache_key] = value
    return value


def _node_executable_realpath(environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    node = shutil.which("node", path=env.get("PATH"))
    if not node:
        return "__missing_node__"
    return os.path.realpath(node)


def _node_version(*, strict: bool = False, environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    node = shutil.which("node", path=env.get("PATH"))
    if not node:
        return "__missing_node__"
    cache_key = _runtime_probe_cache_key("node_version", os.path.realpath(node), env)
    cached = _RUNTIME_FINGERPRINT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            [node, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=dict(env),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if strict:
            raise LongGateFingerprintError(f"node version is required for long gate fingerprint: {exc}") from exc
        return "__node_version_unavailable__"
    if int(completed.returncode) != 0:
        if strict:
            detail = str(completed.stderr or completed.stdout or "").strip() or f"returncode={completed.returncode}"
            raise LongGateFingerprintError(f"node version is required for long gate fingerprint: {detail}")
        return "__node_version_unavailable__"
    value = str(completed.stdout or "").strip()
    _RUNTIME_FINGERPRINT_CACHE[cache_key] = value
    return value


def _node_browser_runtime_capability(*, strict: bool = False, environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    node = shutil.which("node", path=env.get("PATH"))
    if not node:
        return "__missing_node__"
    cache_key = _runtime_probe_cache_key("node_browser_runtime_capability", os.path.realpath(node), env)
    cached = _RUNTIME_FINGERPRINT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    capability_script = (
        "const missing = [];"
        "if (typeof fetch !== 'function') missing.push('fetch');"
        "if (typeof WebSocket !== 'function') missing.push('WebSocket');"
        "if (missing.length) { console.error('missing ' + missing.join(',')); process.exit(1); }"
        "console.log('fetch/WebSocket available');"
    )
    try:
        completed = subprocess.run(
            [node, "-e", capability_script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=dict(env),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        if strict:
            raise LongGateFingerprintError(
                f"node browser runtime capability is required for long gate fingerprint: {exc}"
            ) from exc
        return "__node_browser_runtime_capability_unavailable__"
    payload = {
        "returncode": int(completed.returncode),
        "stdout": str(completed.stdout or "").strip(),
        "stderr": str(completed.stderr or "").strip(),
    }
    if int(completed.returncode) != 0:
        if strict:
            raise LongGateFingerprintError(
                "node browser runtime capability is required for long gate fingerprint: "
                + json.dumps(payload, ensure_ascii=False, sort_keys=True)
            )
        return "__node_browser_runtime_capability_failed__:" + stable_json_hash(payload)
    value = "passed:" + stable_json_hash(payload)
    _RUNTIME_FINGERPRINT_CACHE[cache_key] = value
    return value


def _pytest_plugin_distribution_versions(*, strict: bool = False) -> str:
    try:
        entry_points = importlib.metadata.entry_points()
        select = getattr(entry_points, "select", None)
        if callable(select):
            pytest_plugins = select(group="pytest11")
        else:  # pragma: no cover - Python 3.8 compatibility path
            pytest_plugins = entry_points.get("pytest11", [])
        rows = []
        for item in cast(Iterable[Any], pytest_plugins):
            distribution = getattr(item, "dist", None)
            dist_name = str(getattr(distribution, "metadata", {}).get("Name", "") or getattr(item, "module", "") or "")
            dist_version = str(getattr(distribution, "version", "") or "")
            rows.append(
                {
                    "name": str(getattr(item, "name", "") or ""),
                    "module": str(getattr(item, "module", "") or ""),
                    "distribution": dist_name,
                    "version": dist_version,
                }
            )
        return stable_json_hash(sorted(rows, key=lambda row: (row["name"], row["module"], row["distribution"])))
    except Exception as exc:
        if strict:
            raise LongGateFingerprintError(f"pytest plugin distribution list is required: {exc}") from exc
        return "__pytest_plugin_distribution_versions_unavailable__"


def _runtime_fingerprint_value(
    key: str,
    *,
    strict: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    repo_root: Optional[str] = None,
) -> Optional[str]:
    if key == "python_executable_realpath":
        return os.path.realpath(sys.executable)
    if key == "python_version":
        return sys.version.splitlines()[0].strip()
    if key == "pytest_version":
        return _pytest_version(strict=strict)
    if key == "pytest_plugin_distribution_versions":
        return _pytest_plugin_distribution_versions(strict=strict)
    if key == "ruff_version":
        return _distribution_version("ruff", strict=strict)
    if key == "pyright_version":
        return _distribution_version("pyright", strict=strict)
    if key == "platform":
        return platform.platform()
    if key == "node_executable_realpath":
        return _node_executable_realpath(environment=environment)
    if key == "git_executable_realpath":
        return _git_executable_realpath(environment=environment)
    if key == "git_version":
        return _git_version(strict=strict, environment=environment)
    if key == "node_version":
        return _node_version(strict=strict, environment=environment)
    if key == "node_browser_runtime_capability":
        return _node_browser_runtime_capability(strict=strict, environment=environment)
    if key == "architecture_scan_cache_metadata":
        return "sha256:" + stable_json_hash(architecture_scan_cache.architecture_scan_cache_metadata(repo_root))
    source = environment if environment is not None else os.environ
    return source.get(str(key))


def fingerprint_environment(
    keys: Sequence[str],
    *,
    strict: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    values = {
        str(key): _runtime_fingerprint_value(
            str(key),
            strict=strict,
            environment=environment,
            repo_root=repo_root,
        )
        for key in list(keys or [])
    }
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
    env_overlay = _normalize_env_overlay(entry.get("env_overlay"))
    effective_environment = {str(key): str(value) for key, value in os.environ.items()}
    effective_environment.update(env_overlay)
    command_payload = {
        "display": entry.get("display"),
        "args": entry.get("args"),
        "capture_output": entry.get("capture_output"),
        "output_policy": entry.get("output_policy"),
        "env_overlay": env_overlay,
    }
    env_keys = [str(key) for key in list(entry.get("env_keys") or [])]
    components = {
        "command_hash": fingerprint_command(command_payload),
        "files": fingerprint_files(_entry_file_scopes(entry), repo_root, strict=strict),
        "environment": fingerprint_environment(
            env_keys,
            strict=strict,
            environment=effective_environment,
            repo_root=repo_root,
        ),
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


def _compact_diff_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return {"summary_hash": stable_json_hash(value)}


def _file_diff_summary(row: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    if row is None:
        return {}
    return {
        "exists": bool(row.get("exists")),
        "kind": str(row.get("kind") or ""),
        "sha256": str(row.get("sha256") or ""),
    }


def _component_payload(fingerprint: Mapping[str, Any], component: str) -> Any:
    components = fingerprint.get("components") if isinstance(fingerprint.get("components"), dict) else {}
    return components.get(component) if isinstance(components, dict) else None


def diff_fingerprint_components(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    changes: List[Dict[str, Any]] = []
    if previous.get("schema_version") != current.get("schema_version"):
        changes.append(
            {
                "component": "schema_version",
                "reason": "fingerprint schema changed",
                "previous": _compact_diff_value(previous.get("schema_version")),
                "current": _compact_diff_value(current.get("schema_version")),
            }
        )

    previous_components_obj = previous.get("components")
    current_components_obj = current.get("components")
    previous_components = cast(
        Mapping[str, Any],
        previous_components_obj if isinstance(previous_components_obj, dict) else {},
    )
    current_components = cast(
        Mapping[str, Any],
        current_components_obj if isinstance(current_components_obj, dict) else {},
    )

    if previous_components.get("command_hash") != current_components.get("command_hash"):
        changes.append(
            {
                "component": "command_hash",
                "reason": "command hash changed",
                "previous": _compact_diff_value(previous_components.get("command_hash")),
                "current": _compact_diff_value(current_components.get("command_hash")),
            }
        )

    previous_files = _files_by_path(previous)
    current_files = _files_by_path(current)
    for path in sorted(set(current_files) - set(previous_files)):
        changes.append(
            {
                "component": "files",
                "reason": "added input file",
                "path": path,
                "current": _file_diff_summary(current_files.get(path)),
            }
        )
    for path in sorted(set(previous_files) - set(current_files)):
        changes.append(
            {
                "component": "files",
                "reason": "removed input file",
                "path": path,
                "previous": _file_diff_summary(previous_files.get(path)),
            }
        )
    for path in sorted(set(previous_files) & set(current_files)):
        before = previous_files[path]
        after = current_files[path]
        if (
            before.get("sha256") != after.get("sha256")
            or before.get("exists") != after.get("exists")
            or before.get("kind") != after.get("kind")
        ):
            changes.append(
                {
                    "component": "files",
                    "reason": "modified input file",
                    "path": path,
                    "previous": _file_diff_summary(before),
                    "current": _file_diff_summary(after),
                }
            )

    previous_environment = _component_payload(previous, "environment")
    current_environment = _component_payload(current, "environment")
    previous_values = previous_environment.get("values") if isinstance(previous_environment, dict) else {}
    current_values = current_environment.get("values") if isinstance(current_environment, dict) else {}
    if not isinstance(previous_values, dict):
        previous_values = {}
    if not isinstance(current_values, dict):
        current_values = {}
    for key in sorted(set(previous_values) | set(current_values)):
        if previous_values.get(key) != current_values.get(key):
            changes.append(
                {
                    "component": "environment",
                    "reason": "environment value changed",
                    "key": str(key),
                    "previous": _compact_diff_value(previous_values.get(key)),
                    "current": _compact_diff_value(current_values.get(key)),
                }
            )
    if (
        isinstance(previous_environment, dict)
        and isinstance(current_environment, dict)
        and previous_environment.get("hash") != current_environment.get("hash")
        and not any(change.get("component") == "environment" for change in changes)
    ):
        changes.append(
            {
                "component": "environment",
                "reason": "environment hash changed",
                "previous": _compact_diff_value(previous_environment.get("hash")),
                "current": _compact_diff_value(current_environment.get("hash")),
            }
        )

    previous_collect = _component_payload(previous, "collect_nodeids")
    current_collect = _component_payload(current, "collect_nodeids")
    if isinstance(previous_collect, dict) or isinstance(current_collect, dict):
        previous_collect_map = previous_collect if isinstance(previous_collect, dict) else {}
        current_collect_map = current_collect if isinstance(current_collect, dict) else {}
        for field in ("exists", "validated", "schema_version", "status", "nodeid_hash", "nodeid_count", "error"):
            if previous_collect_map.get(field) != current_collect_map.get(field):
                changes.append(
                    {
                        "component": "collect_nodeids",
                        "reason": "collect nodeids field changed",
                        "field": field,
                        "previous": _compact_diff_value(previous_collect_map.get(field)),
                        "current": _compact_diff_value(current_collect_map.get(field)),
                    }
                )

    previous_outputs = _component_payload(previous, "output_result_files")
    current_outputs = _component_payload(current, "output_result_files")
    previous_paths = previous_outputs.get("paths") if isinstance(previous_outputs, dict) else []
    current_paths = current_outputs.get("paths") if isinstance(current_outputs, dict) else []
    if not isinstance(previous_paths, list):
        previous_paths = []
    if not isinstance(current_paths, list):
        current_paths = []
    for path in sorted(set(str(item) for item in current_paths) - set(str(item) for item in previous_paths)):
        changes.append({"component": "output_result_files", "reason": "added output result file", "path": path})
    for path in sorted(set(str(item) for item in previous_paths) - set(str(item) for item in current_paths)):
        changes.append({"component": "output_result_files", "reason": "removed output result file", "path": path})
    if (
        isinstance(previous_outputs, dict)
        and isinstance(current_outputs, dict)
        and previous_outputs.get("hash") != current_outputs.get("hash")
        and not any(change.get("component") == "output_result_files" for change in changes)
    ):
        changes.append(
            {
                "component": "output_result_files",
                "reason": "output result files hash changed",
                "previous": _compact_diff_value(previous_outputs.get("hash")),
                "current": _compact_diff_value(current_outputs.get("hash")),
            }
        )

    known_components = {"command_hash", "files", "environment", "collect_nodeids", "output_result_files"}
    for component in sorted((set(previous_components) | set(current_components)) - known_components):
        if stable_json_hash(previous_components.get(component)) != stable_json_hash(current_components.get(component)):
            changes.append(
                {
                    "component": str(component),
                    "reason": "fingerprint component changed",
                    "previous": _compact_diff_value(previous_components.get(component)),
                    "current": _compact_diff_value(current_components.get(component)),
                }
            )

    if previous.get("hash") != current.get("hash") and not changes:
        changes.append({"component": "fingerprint", "reason": "input fingerprint changed"})
    return {"changed": bool(changes), "components": changes}


def diff_fingerprints(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    if previous.get("hash") == current.get("hash"):
        return {"changed": False, "reasons": []}

    diff = diff_fingerprint_components(previous, current)
    reasons: List[str] = []
    for change in list(diff.get("components") or []):
        component = str(change.get("component") or "")
        reason = str(change.get("reason") or "input fingerprint changed")
        if component == "files" and change.get("path"):
            reasons.append(f"{reason}: {change.get('path')}")
        elif component == "environment" and change.get("key"):
            reasons.append(f"environment changed: {change.get('key')}")
        elif component == "collect_nodeids" and change.get("field"):
            reasons.append(f"collect_nodeids changed: {change.get('field')}")
        elif component == "output_result_files" and change.get("path"):
            reasons.append(f"{reason}: {change.get('path')}")
        else:
            reasons.append(reason)

    if not reasons:
        reasons.append("input fingerprint changed")
    return {"changed": True, "reasons": reasons, "components": list(diff.get("components") or [])}
