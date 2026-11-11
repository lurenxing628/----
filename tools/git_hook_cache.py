#!/usr/bin/env python3
"""Strict local caches for repository git hooks.

These caches live under .git/aps-hook-cache and only speed up local hooks.
They are not quality gate proof and they are never written into evidence/.
"""

from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from tools.long_gate_fingerprint import (
    _git_executable_realpath,
    _git_version,
    _powershell_executable_realpath,
    _powershell_version,
    _resolve_node_executable,
)
from tools.long_gate_schema import (
    PRIVATE_ENVIRONMENT_KEYS,
    PUBLIC_ENVIRONMENT_KEYS,
    SensitiveSourceError,
    content_equal,
    decode_nul_paths,
    private_environment_value,
    read_file_content,
)
from tools.test_registry_data import REQUIRED_REGRESSION_COMMON_SCOPES, REQUIRED_REGRESSION_GROUPS

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_SCHEMA_VERSION = 2
STAGED_RUFF_CACHE_NAME = "staged-ruff.v2.json"
PRE_PUSH_DAILY_CACHE_NAME = "pre-push-daily.v2.json"

HOOK_CACHE_TOOL_PATHS = (
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "tools/git_hook_cache.py",
    "tools/git_hook_checks.py",
)
DAILY_GATE_TOOL_PATHS = (
    ".pre-commit-config.yaml",
    "pyproject.toml",
    "pytest.ini",
    ".flake8",
    ".importlinter",
    "conftest.py",
    "tests/conftest.py",
    "scripts/run_daily_quality_gate.py",
    "tools/git_hook_cache.py",
    "tools/git_hook_checks.py",
    "tools/test_registry.py",
    "tools/test_registry_data.py",
)
_DAILY_PYTHON_IDENT_KEYS = frozenset(
    {
        "python_executable_realpath",
        "python_version",
        "pytest_version",
        "pytest_plugin_distribution_versions",
    }
)
_DAILY_RUNTIME_PROBE_KEYS = frozenset(
    {
        "platform",
        "git_executable_realpath",
        "git_version",
        "node_executable_realpath",
        "node_version",
        "powershell_executable_realpath",
        "powershell_version",
    }
)


def _daily_gate_env_keys() -> Tuple[str, ...]:
    """Classify every registry env key once; an unclassified key is a registry defect."""
    configured = tuple(
        dict.fromkeys(
            (
                *REQUIRED_REGRESSION_COMMON_SCOPES.get("env_keys", ()),
                *(item for group in REQUIRED_REGRESSION_GROUPS for item in group.get("env_keys", ())),
                "PYTHONHASHSEED",
            )
        )
    )
    unsupported = sorted(
        set(configured)
        - _DAILY_PYTHON_IDENT_KEYS
        - _DAILY_RUNTIME_PROBE_KEYS
        - PUBLIC_ENVIRONMENT_KEYS
        - PRIVATE_ENVIRONMENT_KEYS
    )
    if unsupported:
        raise RuntimeError("environment keys require a public allowlist entry: " + ", ".join(unsupported))
    return tuple(key for key in configured if key in PUBLIC_ENVIRONMENT_KEYS)


DAILY_GATE_ENV_KEYS: Tuple[str, ...] = _daily_gate_env_keys()
_PYTEST_PLUGIN_VERSIONS_CACHE: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
_PYTEST_PLUGIN_PROBE_CODE = (
    "import importlib.metadata as m, json\n"
    "rows = {}\n"
    "for dist in m.distributions():\n"
    "    name = str(dist.metadata['Name'] or '').strip()\n"
    "    version = str(dist.version or '').strip()\n"
    "    eps = [ep for ep in dist.entry_points if ep.group == 'pytest11']\n"
    "    if name and ('pytest' in name.lower() or eps):\n"
    "        rows[name.lower()] = {'name': name, 'version': version, 'plugins': sorted(str(ep.name) for ep in eps)}\n"
    "print(json.dumps([rows[k] for k in sorted(rows)], ensure_ascii=False, sort_keys=True))\n"
)


class HookCacheError(RuntimeError):
    pass


def _run_git_bytes(args: Sequence[str]) -> bytes:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        stderr = bytes(completed.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = bytes(completed.stdout or b"").decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or "git command failed"
        raise HookCacheError(f"git {' '.join(args)} 失败：{detail}")
    return bytes(completed.stdout or b"")


def _run_git(args: Sequence[str]) -> str:
    return _run_git_bytes(args).decode("utf-8", errors="replace")


def _git_common_dir() -> Path:
    raw = _run_git(["rev-parse", "--git-common-dir"]).strip()
    if not raw:
        raise HookCacheError("无法读取 git common dir")
    path = Path(raw)
    if not path.is_absolute():
        path = REPO_ROOT / path
    return path


def hook_cache_dir() -> Path:
    cache_dir = _git_common_dir() / "aps-hook-cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def cache_path(name: str) -> Path:
    return hook_cache_dir() / name


def _load_json(path: Path) -> Optional[Dict[str, Any]]:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return dict(payload)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
        json.dump(dict(payload), handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
    os.replace(str(tmp_path), str(path))


def _file_contents(paths: Iterable[str]) -> Dict[str, Optional[str]]:
    rows: Dict[str, Optional[str]] = {}
    for rel_path in sorted({str(path) for path in paths if path}):
        abs_path = REPO_ROOT / rel_path
        if abs_path.is_file():
            try:
                rows[rel_path] = read_file_content(str(abs_path))
            except SensitiveSourceError as exc:
                raise HookCacheError(str(exc)) from exc
        else:
            rows[rel_path] = None
    return rows


def _python_identity(executable: str) -> Dict[str, str]:
    abspath = os.path.abspath(str(executable or sys.executable))
    realpath = os.path.realpath(abspath)
    completed = subprocess.run(
        [abspath, "-c", "import sys; print(sys.version.replace('\\n', ' '))"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    version = str(completed.stdout or "").strip() if completed.returncode == 0 else ""
    return {
        "executable_abspath": abspath,
        "executable_realpath": realpath,
        "version": version,
    }


def _tool_version(executable: str, module: str) -> str:
    completed = subprocess.run(
        [executable, "-m", module, "--version"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return f"returncode={completed.returncode};{str(completed.stderr or completed.stdout or '').strip()}"
    return str(completed.stdout or "").strip()


def staged_paths() -> List[str]:
    return decode_nul_paths(_run_git_bytes(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]))


def staged_python_paths() -> Tuple[str, ...]:
    return tuple(sorted(path for path in staged_paths() if path.endswith(".py")))


def staged_tree_hash() -> str:
    return _run_git(["write-tree"]).strip()


def head_tree_hash() -> str:
    return _run_git(["rev-parse", "HEAD^{tree}"]).strip()


def git_status_lines() -> List[str]:
    output = _run_git(["status", "--short"])
    return [line for line in output.splitlines() if line.strip()]


def _cache_key_payload(
    *,
    kind: str,
    executable: str,
    extra: Mapping[str, Any],
    watched_paths: Sequence[str],
    tool_modules: Sequence[str] = ("ruff",),
) -> Dict[str, Any]:
    tool_versions = {str(module): _tool_version(executable, str(module)) for module in list(tool_modules or ())}
    return {
        "schema_version": CACHE_SCHEMA_VERSION,
        "kind": kind,
        "extra": dict(extra),
        "python": _python_identity(executable),
        "ruff_version": tool_versions.get("ruff", ""),
        "tool_versions": tool_versions,
        "watched_files": _file_contents(watched_paths),
    }


def _cache_matches(path: Path, key_payload: Mapping[str, Any]) -> bool:
    return _cache_payload_matches(_load_json(path), key_payload)


def _cache_payload_matches(payload: Optional[Mapping[str, Any]], key_payload: Mapping[str, Any]) -> bool:
    return bool(payload and payload.get("schema_version") == CACHE_SCHEMA_VERSION
                and payload.get("status") == "passed" and "key_payload" in payload
                and content_equal(payload["key_payload"], dict(key_payload)))


def _write_pass_cache(path: Path, *, key_payload: Mapping[str, Any], extra: Mapping[str, Any]) -> None:
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "status": "passed",
        "key_payload": dict(key_payload),
        "extra": dict(extra),
        "written_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "does_not_claim": "clean_worktree_final_proof",
    }
    _write_json(path, payload)


def _export_index_to_temp(prefix: Path) -> None:
    target_prefix = str(prefix)
    if not target_prefix.endswith(os.sep):
        target_prefix += os.sep
    completed = subprocess.run(
        ["git", "checkout-index", "--all", "--prefix", target_prefix],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = str(completed.stderr or completed.stdout or "git checkout-index failed").strip()
        raise HookCacheError(f"导出暂存区失败：{detail}")


def run_staged_ruff(executable: str) -> int:
    targets = staged_python_paths()
    if not targets:
        print("[git-hook-cache] staged ruff: no staged Python files, skipped", flush=True)
        return 0

    tree_hash = ""
    path: Optional[Path] = None
    key_payload: Optional[Dict[str, Any]] = None
    try:
        tree_hash = staged_tree_hash()
        key_payload = _cache_key_payload(
            kind="staged-ruff",
            executable=executable,
            watched_paths=HOOK_CACHE_TOOL_PATHS,
            extra={
                "staged_tree": tree_hash,
                "staged_python_paths": list(targets),
            },
        )
        path = cache_path(STAGED_RUFF_CACHE_NAME)
        if _cache_matches(path, key_payload):
            print("[git-hook-cache] staged ruff: reuse passed cache for unchanged staged tree", flush=True)
            return 0
    except HookCacheError as exc:
        print(f"[git-hook-cache] staged ruff cache unavailable: {exc}", flush=True)
        key_payload = None

    temp_dir = tempfile.mkdtemp(prefix="aps-staged-ruff-")
    try:
        temp_root = Path(temp_dir)
        _export_index_to_temp(temp_root)
        command = [executable, "-m", "ruff", "check", "--force-exclude", "--", *list(targets)]
        print("[git-hook-cache] staged ruff:", " ".join(command), flush=True)
        returncode = subprocess.call(command, cwd=str(temp_root), env=_hook_env())
        if int(returncode) == 0 and key_payload is not None and path is not None:
            _write_pass_cache(
                path,
                key_payload=key_payload,
                extra={"staged_tree": tree_hash, "staged_python_paths": list(targets)},
            )
        return int(returncode)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _hook_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _daily_scope_cache_extra(scope_payload: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    payload = dict(scope_payload or {})
    impact = payload.get("impact_pytest")
    ruff = payload.get("ruff")
    impact_payload = dict(impact) if isinstance(impact, Mapping) else {}
    ruff_payload = dict(ruff) if isinstance(ruff, Mapping) else {}
    return {
        "scope_known": bool(payload.get("scope_known")),
        "scope_reason": str(payload.get("reason") or ""),
        "changed_paths": list(payload.get("changed_paths") or []),
        "impact_pytest_target_paths": list(impact_payload.get("target_paths") or []),
        "impact_pytest_all_required_groups": bool(impact_payload.get("all_required_groups")),
        "ruff_target_paths": list(ruff_payload.get("target_paths") or []),
        "ruff_all_files": bool(ruff_payload.get("all_files")),
        "scope_payload": payload,
    }


def _daily_ref_contexts_cache_extra(ref_contexts: Optional[Sequence[Mapping[str, Any]]]) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    for raw_context in list(ref_contexts or []):
        context = dict(raw_context or {})
        rows.append(
            {
                "local_ref": str(context.get("local_ref") or ""),
                "local_sha": str(context.get("local_sha") or ""),
                "remote_ref": str(context.get("remote_ref") or ""),
                "remote_sha": str(context.get("remote_sha") or ""),
            }
        )
    return sorted(rows, key=lambda item: (
        item["remote_ref"], item["local_ref"], item["local_sha"], item["remote_sha"],
    ))


def _collect_in_process_pytest_plugins() -> List[Dict[str, Any]]:
    rows: Dict[str, Dict[str, Any]] = {}
    for dist in importlib.metadata.distributions():
        name = str(dist.metadata["Name"] or "").strip()
        version = str(dist.version or "").strip()
        eps = [ep for ep in dist.entry_points if ep.group == "pytest11"]
        if name and ("pytest" in name.lower() or eps):
            rows[name.lower()] = {
                "name": name,
                "version": version,
                "plugins": sorted(str(ep.name) for ep in eps),
            }
    return [rows[key] for key in sorted(rows)]


def _pytest_plugin_versions(executable: str, env: Optional[Mapping[str, str]] = None) -> List[Dict[str, Any]]:
    effective_env = dict(_hook_env() if env is None else env)
    abspath = os.path.abspath(str(executable or sys.executable))
    realpath = os.path.realpath(abspath)
    pythonpath = str(effective_env.get("PYTHONPATH") or "")
    cache_key = (os.path.normcase(abspath), os.path.normcase(realpath), pythonpath)
    cached = _PYTEST_PLUGIN_VERSIONS_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if (
        os.path.normcase(abspath) == os.path.normcase(os.path.abspath(sys.executable))
        and pythonpath == str(os.environ.get("PYTHONPATH") or "")
    ):
        rows = _collect_in_process_pytest_plugins()
        _PYTEST_PLUGIN_VERSIONS_CACHE[cache_key] = rows
        return rows
    completed = subprocess.run(
        [abspath, "-c", _PYTEST_PLUGIN_PROBE_CODE],
        cwd=str(REPO_ROOT),
        env=effective_env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return [{"error": f"returncode={completed.returncode};{str(completed.stderr or completed.stdout or '').strip()}"}]
    try:
        parsed = json.loads(str(completed.stdout or "").strip() or "[]")
    except ValueError as exc:
        return [{"error": f"invalid_json={exc}"}]
    if not isinstance(parsed, list):
        return [{"error": "invalid_payload"}]
    rows = [dict(item) for item in parsed if isinstance(item, dict)]
    _PYTEST_PLUGIN_VERSIONS_CACHE[cache_key] = rows
    return rows


def _daily_pytest_environment(env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    effective_env = _hook_env() if env is None else env
    private_keys = sorted(key for key in PRIVATE_ENVIRONMENT_KEYS if private_environment_value(effective_env, key))
    if private_keys:
        raise HookCacheError(
            "private environment values remain in memory; hook cache unavailable: " + ", ".join(private_keys)
        )
    values: Dict[str, Any] = {key: effective_env.get(key) for key in DAILY_GATE_ENV_KEYS}
    values["platform"] = platform.platform()
    values["git_executable_realpath"] = _git_executable_realpath(environment=effective_env)
    values["git_version"] = _git_version(strict=False, environment=effective_env)
    node_path, node_version = _resolve_node_executable(effective_env)
    values["node_executable_realpath"] = node_path or node_version
    values["node_version"] = node_version
    values["powershell_executable_realpath"] = _powershell_executable_realpath(environment=effective_env)
    values["powershell_version"] = _powershell_version(strict=False, environment=effective_env)
    return values


def _esbuild_vendor_cache_identity(environment: Mapping[str, str]) -> Dict[str, Any]:
    manifest_path = REPO_ROOT / "scripts/workbench/esbuild-manifest.json"
    if not manifest_path.is_file():
        return {"required": False}
    from scripts.workbench.vendor_react import verify_esbuild_vendor

    node_bin, _ = _resolve_node_executable(environment)
    try:
        verified = verify_esbuild_vendor(REPO_ROOT, manifest_path=manifest_path, node_executable=node_bin)
        files: Dict[str, List[int]] = {}
        for rel_path in (
            "scripts/workbench/esbuild-manifest.json",
            verified["package_json"],
            "vendor/node_modules/esbuild/lib/main.js",
            "vendor/node_modules/esbuild/bin/esbuild",
            verified["platform_package_json"],
            verified["binary"],
        ):
            st = (REPO_ROOT / rel_path).stat()
            files[rel_path] = [int(st.st_size), int(st.st_mtime_ns)]
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        return {"required": True, "verified": False, "error": str(exc)}
    return {
        "required": True,
        "verified": True,
        "platform": verified["platform"],
        "version": verified["version"],
        "files": files,
    }


def daily_gate_cache_key(
    executable: str,
    *,
    remote_name: str = "",
    remote_ref: str = "",
    scope_payload: Optional[Mapping[str, Any]] = None,
    ref_contexts: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    scope_extra = _daily_scope_cache_extra(scope_payload)
    contexts = _daily_ref_contexts_cache_extra(ref_contexts)
    env = _hook_env()
    # Target refs execute in their committed worktrees; manual runs use this checkout.
    source_extra = {} if contexts else {"head_tree": head_tree_hash(), "git_status_short": git_status_lines()}
    key_payload = _cache_key_payload(
        kind="pre-push-daily",
        executable=executable,
        watched_paths=DAILY_GATE_TOOL_PATHS,
        tool_modules=("ruff", "pytest"),
        extra={
            **source_extra,
            "remote_name": str(remote_name or ""),
            "remote_ref": str(remote_ref or ""),
            "ref_contexts": contexts,
            "pytest_env": _daily_pytest_environment(env),
            "pytest_plugins": _pytest_plugin_versions(executable, env),
            "esbuild_vendor": _esbuild_vendor_cache_identity(env),
            **scope_extra,
        },
    )
    return key_payload


def pre_push_daily_cache_hit(
    executable: str,
    *,
    remote_name: str = "",
    remote_ref: str = "",
    scope_payload: Optional[Mapping[str, Any]] = None,
    ref_contexts: Optional[Sequence[Mapping[str, Any]]] = None,
    key_payload: Optional[Mapping[str, Any]] = None,
) -> bool:
    path = cache_path(PRE_PUSH_DAILY_CACHE_NAME)
    cached = _load_json(path)
    if not cached or cached.get("status") != "passed" or (not ref_contexts and git_status_lines()):
        return False
    current_key = key_payload if key_payload is not None else daily_gate_cache_key(
        executable,
        remote_name=remote_name,
        remote_ref=remote_ref,
        scope_payload=scope_payload,
        ref_contexts=ref_contexts,
    )
    return _cache_payload_matches(cached, current_key)


def write_pre_push_daily_cache(
    executable: str,
    *,
    remote_name: str = "",
    remote_ref: str = "",
    scope_payload: Optional[Mapping[str, Any]] = None,
    ref_contexts: Optional[Sequence[Mapping[str, Any]]] = None,
    key_payload: Optional[Mapping[str, Any]] = None,
) -> None:
    if not ref_contexts and git_status_lines():
        raise HookCacheError("pre-push daily gate pass cache 只能在干净工作区写入")
    current_key = key_payload if key_payload is not None else daily_gate_cache_key(
        executable,
        remote_name=remote_name,
        remote_ref=remote_ref,
        scope_payload=scope_payload,
        ref_contexts=ref_contexts,
    )
    _write_pass_cache(
        cache_path(PRE_PUSH_DAILY_CACHE_NAME),
        key_payload=current_key,
        extra={
            "remote_name": str(remote_name or ""),
            "remote_ref": str(remote_ref or ""),
            "changed_paths": current_key["extra"]["changed_paths"],
            "impact_pytest_target_paths": current_key["extra"]["impact_pytest_target_paths"],
            "ruff_target_paths": current_key["extra"]["ruff_target_paths"],
        },
    )
