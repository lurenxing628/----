from __future__ import annotations

import fnmatch
import glob
import importlib.metadata
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, cast

from tools.long_gate_paths import is_within_repo, real_repo_root
from tools.long_gate_schema import LONG_GATE_FINGERPRINT_SCHEMA_VERSION, content_equal, read_file_content
from tools.quality_gate_shared import (
    QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL,
    normalize_quality_gate_command,
)

_EXPECTED_COLLECT_NODEIDS_SCHEMA_VERSION = 2
_CURRENT_FULL_TEST_DEBT_REL = QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/")
_RUNTIME_FINGERPRINT_CACHE: Dict[Tuple[str, str, Tuple[Tuple[str, str], ...]], Any] = {}
ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION = 2
RUNTIME_FINGERPRINT_KEYS = frozenset(
    {
        "python_executable_realpath",
        "python_version",
        "pytest_version",
        "pytest_plugin_distribution_versions",
        "ruff_version",
        "pyright_version",
        "platform",
        "node_executable_realpath",
        "powershell_executable_realpath",
        "powershell_version",
        "git_executable_realpath",
        "git_version",
        "node_version",
        "architecture_scan_cache_metadata",
    }
)


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


def _abs_for_scope_path(path: str, repo_root: str) -> str:
    normalized = _normalize_scope_path(path)
    if os.path.isabs(normalized):
        return normalized
    return os.path.join(real_repo_root(repo_root), normalized.replace("/", os.sep))


def _candidate_paths_for_scope(scope: str, repo_root: str, tracked: Set[str], untracked: Set[str]) -> Set[str]:
    normalized_scope = _normalize_scope_path(scope)
    if not normalized_scope:
        return set()
    if not _has_glob_chars(normalized_scope):
        return {normalized_scope}

    candidates = {path for path in set(tracked) | set(untracked) if fnmatch.fnmatch(path, normalized_scope)}
    root = real_repo_root(repo_root)
    glob_pattern = normalized_scope if os.path.isabs(normalized_scope) else os.path.join(root, normalized_scope)
    if not is_within_repo(glob_pattern, root):
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
    if not os.path.islink(abs_path) and not is_within_repo(abs_path, repo_root):
        return {
            "path": normalized,
            "exists": False,
            "kind": "outside_repo",
            "size": 0,
            "mode": "",
            "source": "outside_repo",
        }
    exists = os.path.lexists(abs_path)
    source = (
        "tracked"
        if normalized in tracked
        else "untracked"
        if normalized in untracked
        else "filesystem"
        if exists
        else "missing"
    )
    if not exists:
        return {"path": normalized, "exists": False, "kind": "missing", "size": 0, "mode": "", "source": source}
    content: Dict[str, Any] = {}
    if os.path.islink(abs_path):
        link_target = os.readlink(abs_path)
        link_realpath = os.path.realpath(abs_path)
        inside = is_within_repo(link_realpath, repo_root)
        kind = "symlink" if inside else "symlink_outside_repo"
        content = {
            "target": link_target,
            "target_realpath": link_realpath,
            "target_inside_repo": inside,
            "target_content_base64": read_file_content(link_realpath)
            if inside and os.path.isfile(link_realpath)
            else "",
        }
        size = len(os.fsencode(link_target))
    elif os.path.isfile(abs_path):
        kind = "file"
        content = {"content_base64": read_file_content(abs_path)}
        size = os.path.getsize(abs_path)
    elif os.path.isdir(abs_path):
        kind, size = "directory", 0
    else:
        kind, size = "other", 0
    return {
        "path": normalized,
        "exists": True,
        "kind": kind,
        "size": int(size),
        "mode": _file_mode(abs_path, kind),
        "source": source,
        **content,
    }


class FingerprintFileSnapshot:
    """File observations shared only within one cache-decision phase."""

    def __init__(self, repo_root: str, *, strict: bool = False) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.strict = strict
        self.sources: Optional[Tuple[Set[str], Set[str], str]] = None
        self.rows: Dict[str, Dict[str, Any]] = {}
        self.scopes: Dict[str, Set[str]] = {}

    def path_sources(self) -> Tuple[Set[str], Set[str], str]:
        if self.sources is None:
            self.sources = _git_path_sources(self.repo_root, strict=self.strict)
        return self.sources

    def file_row(self, path: str) -> Dict[str, Any]:
        if path not in self.rows:
            tracked, untracked, _status = self.path_sources()
            self.rows[path] = _fingerprint_one_file(path, self.repo_root, tracked, untracked)
        return dict(self.rows[path])

    def scope_paths(self, scope: str) -> Set[str]:
        if scope not in self.scopes:
            tracked, untracked, _status = self.path_sources()
            self.scopes[scope] = _candidate_paths_for_scope(scope, self.repo_root, tracked, untracked)
        return self.scopes[scope]


def fingerprint_files(
    paths_or_patterns: Sequence[str],
    repo_root: str,
    *,
    strict: bool = False,
    file_snapshot: Optional[FingerprintFileSnapshot] = None,
) -> Dict[str, Any]:
    root = os.path.abspath(repo_root)
    snapshot = file_snapshot or FingerprintFileSnapshot(root, strict=strict)
    if snapshot.repo_root != root or snapshot.strict != strict:
        raise ValueError("file snapshot belongs to a different fingerprint phase")
    tracked, untracked, git_source_status = snapshot.path_sources()
    rel_paths: Set[str] = set()
    for scope in list(paths_or_patterns or []):
        rel_paths.update(snapshot.scope_paths(str(scope)))

    files = [snapshot.file_row(path) for path in sorted(rel_paths)]
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
        "paths": path_rows,
        "files": files,
    }


def fingerprint_command(command: Mapping[str, Any]) -> Dict[str, Any]:
    normalized = normalize_quality_gate_command(command)
    if "SECRET_KEY" in normalized["env_overlay"]:
        raise LongGateFingerprintError(
            "SECRET_KEY must remain in the process environment, not the persisted command overlay"
        )
    return normalized


def pytest_distribution_version(*, strict: bool = False) -> str:
    return _distribution_version("pytest", strict=strict)


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


def _runtime_probe_cache_key(
    probe: str, exe_realpath: str, environment: Mapping[str, str]
) -> Tuple[str, str, Tuple[Tuple[str, str], ...]]:
    """Deduplicate successful probes with exact inputs only within this process."""
    return (probe, exe_realpath, tuple(sorted((str(key), str(value)) for key, value in environment.items())))


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


def _probe_node_version(resolved: str, env: Mapping[str, str]) -> Optional[str]:
    cache_key = _runtime_probe_cache_key("node_version", resolved, env)
    cached = _RUNTIME_FINGERPRINT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    probe_env = dict(env)
    node_dir = os.path.dirname(resolved)
    probe_env["PATH"] = f"{node_dir}{os.pathsep}{probe_env.get('PATH', '')}"
    try:
        completed = subprocess.run(
            [resolved, "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
            env=probe_env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    value = str(completed.stdout or "").strip()
    if int(completed.returncode) == 0 and value.startswith("v"):
        _RUNTIME_FINGERPRINT_CACHE[cache_key] = value
        return value
    return None


def _resolve_node_executable(environment: Optional[Mapping[str, str]] = None) -> Tuple[Optional[str], str]:
    env = _effective_environment(environment)
    resolution_key = _runtime_probe_cache_key("node_resolution", "", env)
    cached_resolution = _RUNTIME_FINGERPRINT_CACHE.get(resolution_key)
    if cached_resolution is not None:
        resolved_cached, version_cached = str(cached_resolution).split("\n", 1)
        return resolved_cached, version_cached
    path = env.get("PATH")
    configured = (env.get("WORKBENCH_NODE") or "").strip()
    if configured:
        resolved_which = shutil.which(configured, path=path)
        if resolved_which:
            candidates = [resolved_which]
        elif os.path.sep in configured or (os.path.altsep and os.path.altsep in configured) or configured.startswith("~"):
            candidates = [os.path.expanduser(configured)]
        else:
            return None, "__missing_node__:" + configured
        missing_marker = "__missing_node__:" + configured
    else:
        candidates = []
        path_entries = [entry for entry in path.split(os.pathsep) if entry] if path is not None else [None]
        for entry in path_entries:
            resolved_which = shutil.which("node", path=entry)
            if resolved_which:
                candidates.append(resolved_which)
        candidates.extend(
            [
                os.path.expanduser("~/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"),
                "/opt/homebrew/bin/node",
                "/usr/local/bin/node",
                os.path.expanduser("~/.nvm/current/bin/node"),
            ]
        )
        candidates.extend(sorted(glob.glob(os.path.expanduser("~/.nvm/versions/node/*/bin/node")), reverse=True))
        missing_marker = "__missing_node__"

    seen: Set[str] = set()
    for candidate in candidates:
        resolved = os.path.realpath(os.path.expanduser(candidate))
        if resolved in seen:
            continue
        seen.add(resolved)
        if not (os.path.isfile(resolved) and os.access(resolved, os.X_OK)):
            continue
        version = _probe_node_version(resolved, env)
        if version is not None:
            _RUNTIME_FINGERPRINT_CACHE[resolution_key] = f"{resolved}\n{version}"
            return resolved, version
    return None, missing_marker


def _powershell_executable_realpath(environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    path = env.get("PATH")
    configured = env.get("APS_TEST_POWERSHELL")
    if configured:
        resolved = shutil.which(configured, path=path)
        if resolved:
            return os.path.realpath(resolved)
        if os.path.sep in configured or (os.path.altsep and os.path.altsep in configured):
            candidate = os.path.realpath(configured)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
        return "__missing_powershell__:" + str(configured)
    resolved = shutil.which("powershell", path=path) or shutil.which("pwsh", path=path)
    if not resolved:
        return "__missing_powershell__"
    return os.path.realpath(resolved)


def _powershell_version(*, strict: bool = False, environment: Optional[Mapping[str, str]] = None) -> str:
    env = _effective_environment(environment)
    powershell = _powershell_executable_realpath(environment=environment)
    if powershell.startswith("__missing_powershell__"):
        return powershell
    cache_key = _runtime_probe_cache_key("powershell_version", powershell, env)
    cached = _RUNTIME_FINGERPRINT_CACHE.get(cache_key)
    if cached is not None:
        return cached
    try:
        completed = subprocess.run(
            [powershell, "-NoProfile", "-NonInteractive", "-Command", "$PSVersionTable.PSVersion.ToString()"],
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
                f"powershell version is required for long gate fingerprint: {exc}"
            ) from exc
        return "__powershell_version_unavailable__"
    if int(completed.returncode) != 0:
        if strict:
            detail = str(completed.stderr or completed.stdout or "").strip() or f"returncode={completed.returncode}"
            raise LongGateFingerprintError(f"powershell version is required for long gate fingerprint: {detail}")
        return "__powershell_version_unavailable__"
    value = str(completed.stdout or "").strip()
    _RUNTIME_FINGERPRINT_CACHE[cache_key] = value
    return value


def _pytest_plugin_distribution_versions(*, strict: bool = False) -> Any:
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
        return sorted(rows, key=lambda row: (row["name"], row["module"], row["distribution"]))
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
) -> Any:
    if key == "python_executable_realpath":
        return os.path.realpath(sys.executable)
    if key == "python_version":
        return sys.version.splitlines()[0].strip()
    if key == "pytest_version":
        return pytest_distribution_version(strict=strict)
    if key == "pytest_plugin_distribution_versions":
        return _pytest_plugin_distribution_versions(strict=strict)
    if key == "ruff_version":
        return _distribution_version("ruff", strict=strict)
    if key == "pyright_version":
        return _distribution_version("pyright", strict=strict)
    if key == "platform":
        return platform.platform()
    if key == "powershell_executable_realpath":
        return _powershell_executable_realpath(environment=environment)
    if key == "powershell_version":
        return _powershell_version(strict=strict, environment=environment)
    if key == "git_executable_realpath":
        return _git_executable_realpath(environment=environment)
    if key == "git_version":
        return _git_version(strict=strict, environment=environment)
    if key == "architecture_scan_cache_metadata":
        from tools import architecture_scan_cache

        return architecture_scan_cache.architecture_scan_cache_metadata(repo_root)
    source = environment if environment is not None else os.environ
    value = source.get(str(key))
    if key == "SECRET_KEY":
        return {"present": value is not None}
    return value


PUBLIC_ENVIRONMENT_KEYS = frozenset(
    {
        "APS_ENV",
        "APS_DB_PATH",
        "APS_LOG_DIR",
        "APS_BACKUP_DIR",
        "APS_EXCEL_TEMPLATE_DIR",
        "APS_HOST",
        "APS_PORT",
        "APS_SHARED_DATA_ROOT",
        "APS_STATIC_VERSION",
        "APS_TEST_POWERSHELL",
        "WERKZEUG_RUN_MAIN",
        "WORKBENCH_NODE",
        "NODE_PATH",
        "NODE_OPTIONS",
        "PATH",
        "VIRTUAL_ENV",
        "PYTHONHOME",
        "PYTHONPATH",
        "PYTHONDONTWRITEBYTECODE",
        "PYTHONUTF8",
        "PYTHONIOENCODING",
        "PYTEST_ADDOPTS",
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
        "PYTEST_PLUGINS",
        "LANG",
        "LC_ALL",
        "CI",
        "APS_FULL_TEST_DEBT_SHARDED",
        "APS_FULL_TEST_DEBT_SHARD_COUNT",
    }
)


def fingerprint_environment(
    keys: Sequence[str],
    *,
    strict: bool = False,
    environment: Optional[Mapping[str, str]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    unsupported = sorted(
        {str(key) for key in keys} - RUNTIME_FINGERPRINT_KEYS - PUBLIC_ENVIRONMENT_KEYS - {"SECRET_KEY"}
    )
    if unsupported:
        raise LongGateFingerprintError("environment keys require a public allowlist entry: " + ", ".join(unsupported))
    key_list = [str(key) for key in list(keys or [])]
    node_resolution = (
        _resolve_node_executable(environment)
        if ("node_executable_realpath" in key_list or "node_version" in key_list)
        else None
    )
    values: Dict[str, Any] = {}
    for key in key_list:
        if node_resolution is not None and key == "node_executable_realpath":
            values[key] = node_resolution[0] or node_resolution[1]
        elif node_resolution is not None and key == "node_version":
            values[key] = node_resolution[1]
        else:
            values[key] = _runtime_fingerprint_value(
                key,
                strict=strict,
                environment=environment,
                repo_root=repo_root,
            )
    return {
        "schema_version": ENVIRONMENT_FINGERPRINT_SCHEMA_VERSION,
        "keys": key_list,
        "values": values,
        "non_reusable_env_keys": [key for key in values if key == "SECRET_KEY" and values[key]["present"]],
    }


def _entry_file_scopes(entry: Mapping[str, Any]) -> List[str]:
    scopes: List[str] = []
    for key in ("input_file_scopes", "config_file_scopes", "tool_file_scopes", "dependency_file_scopes"):
        scopes.extend(str(item) for item in list(entry.get(key) or []))
    return list(dict.fromkeys(scopes))


def _entry_file_scopes_for_fingerprint(entry: Mapping[str, Any]) -> List[str]:
    scopes = _entry_file_scopes(entry)
    if str(entry.get("entry_id") or "") == "required_regressions":
        return [scope for scope in scopes if scope.replace("\\", "/") != _CURRENT_FULL_TEST_DEBT_REL]
    return scopes


def _entry_output_result_files(entry: Mapping[str, Any]) -> List[str]:
    return list(dict.fromkeys(str(item).replace("\\", "/") for item in list(entry.get("output_result_files") or [])))


def _collect_nodeids_component(repo_root: str) -> Dict[str, Any]:
    from tools.long_gate_collect import COLLECT_NODEIDS_REL

    rel_path = COLLECT_NODEIDS_REL
    abs_path = _abs_for_scope_path(rel_path, repo_root)
    component: Dict[str, Any] = {
        "path": rel_path,
        "exists": os.path.isfile(abs_path),
        "validated": False,
        "schema_version": None,
        "status": "",
        "nodeids": [],
        "nodeids_by_file": {},
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
    component.update(
        {
            key: payload.get(key)
            for key in (
                "schema_version",
                "status",
                "nodeids",
                "nodeids_by_file",
                "nodeid_count",
                "pytest_version",
                "collect_stdout_content",
                "collect_stdout_log_path",
            )
        }
    )
    nodeids = payload.get("nodeids")
    if component["schema_version"] != _EXPECTED_COLLECT_NODEIDS_SCHEMA_VERSION:
        component["error"] = "collect_nodeids schema_version is invalid"
    elif not isinstance(nodeids, list) or any(not isinstance(item, str) for item in nodeids):
        component["error"] = "collect_nodeids nodeids must be a list of strings"
    elif component["nodeid_count"] != len(nodeids):
        component["error"] = "collect_nodeids nodeid_count does not match nodeids"
    elif not content_equal(component["nodeids_by_file"], _collect_nodeids_by_file(nodeids)):
        component["error"] = "collect_nodeids nodeids_by_file does not match nodeids"
    elif not isinstance(payload.get("collect_stdout_content"), str):
        component["error"] = "collect_nodeids collect_stdout_content is missing"
    else:
        from tools.quality_gate_shared import parse_pytest_collect_nodeids

        if not content_equal(parse_pytest_collect_nodeids(payload["collect_stdout_content"]), nodeids):
            component["error"] = "collect_nodeids stdout does not match nodeids"
        else:
            log_path = str(payload.get("collect_stdout_log_path") or "")
            if log_path:
                from tools.long_gate_paths import resolve_repo_path

                try:
                    log_abs = resolve_repo_path(repo_root, log_path, description="collect stdout log path")
                    with open(log_abs, "rb") as handle:
                        log_bytes = handle.read()
                    if log_bytes != payload["collect_stdout_content"].encode("utf-8"):
                        component["error"] = "collect_nodeids stdout log content changed"
                except (OSError, ValueError) as exc:
                    component["error"] = str(exc)
            component["validated"] = not bool(component["error"])
    return component


def _required_full_test_debt_component(repo_root: str) -> Dict[str, Any]:
    rel_path = _CURRENT_FULL_TEST_DEBT_REL
    abs_path = _abs_for_scope_path(rel_path, repo_root)
    component: Dict[str, Any] = {
        "path": rel_path,
        "exists": os.path.isfile(abs_path),
        "validated": False,
        "verification": None,
        "error": "",
    }
    if not component["exists"]:
        return component
    try:
        with open(abs_path, encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            raise ValueError("current_full_test_debt payload is not an object")
        from tools.verify_required_regressions_from_full_test_debt import verify_required_regressions_from_payload

        verification = verify_required_regressions_from_payload(payload)
    except Exception as exc:
        component["error"] = str(exc)
        return component
    component.update({"validated": True, "verification": verification})
    return component


def fingerprint_entry(
    entry: Mapping[str, Any],
    repo_root: str,
    *,
    strict: bool = False,
    file_snapshot: Optional[FingerprintFileSnapshot] = None,
) -> Dict[str, Any]:
    command_payload = fingerprint_command(entry)
    env_overlay = command_payload["env_overlay"]
    effective_environment = {str(key): str(value) for key, value in os.environ.items()}
    effective_environment.update(env_overlay)
    env_keys = [str(key) for key in list(entry.get("env_keys") or [])]
    components = {
        "command": command_payload,
        "files": fingerprint_files(
            _entry_file_scopes_for_fingerprint(entry), repo_root, strict=strict, file_snapshot=file_snapshot
        ),
        "environment": fingerprint_environment(
            env_keys,
            strict=strict,
            environment=effective_environment,
            repo_root=repo_root,
        ),
        "output_result_files": {
            "paths": _entry_output_result_files(entry),
        },
    }
    if str(entry.get("entry_id") or "") == "full_test_debt":
        components["collect_nodeids"] = _collect_nodeids_component(repo_root)
    if str(entry.get("entry_id") or "") == "required_regressions":
        components["required_full_test_debt"] = _required_full_test_debt_component(repo_root)
    payload = {
        "schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "components": components,
    }
    return payload


def _files_by_path(fingerprint: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    components = fingerprint.get("components") if isinstance(fingerprint.get("components"), dict) else {}
    files_component = components.get("files") if isinstance(components, dict) else {}
    files = files_component.get("files") if isinstance(files_component, dict) else []
    return {str(row.get("path") or ""): row for row in list(files or []) if isinstance(row, dict)}


def diff_fingerprint_components(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    changes: List[Dict[str, Any]] = []
    if not content_equal(previous.get("schema_version"), current.get("schema_version")):
        changes.append(
            {
                "component": "schema_version",
                "reason": "fingerprint schema changed",
                "previous": previous.get("schema_version"),
                "current": current.get("schema_version"),
            }
        )
    before = previous.get("components")
    if not isinstance(before, dict):
        before = {}
    after = current.get("components")
    if not isinstance(after, dict):
        after = {}
    previous_files, current_files = _files_by_path(previous), _files_by_path(current)
    for path in sorted(set(previous_files) | set(current_files)):
        old, new = previous_files.get(path), current_files.get(path)
        if not content_equal(old, new):
            reason = (
                "added input file" if old is None else "removed input file" if new is None else "modified input file"
            )
            changes.append({"component": "files", "reason": reason, "path": path, "previous": old, "current": new})
    for component in sorted((set(before) | set(after)) - {"files"}):
        if not content_equal(before.get(component), after.get(component)):
            changes.append(
                {
                    "component": component,
                    "reason": "command identity changed" if component == "command" else "fingerprint component changed",
                    "previous": before.get(component),
                    "current": after.get(component),
                }
            )
    if not content_equal(previous, current) and not changes:
        changes.append({"component": "fingerprint", "reason": "input fingerprint changed"})
    return {"changed": bool(changes), "components": changes}


def diff_fingerprints(previous: Mapping[str, Any], current: Mapping[str, Any]) -> Dict[str, Any]:
    if content_equal(previous, current):
        return {"changed": False, "reasons": [], "components": []}
    diff = diff_fingerprint_components(previous, current)
    reasons = [
        str(row["reason"]) + (": " + str(row["path"]) if row.get("path") else ": " + str(row["component"]))
        for row in diff["components"]
    ]
    return {"changed": True, "reasons": reasons or ["input fingerprint changed"], "components": diff["components"]}
