#!/usr/bin/env python3
"""Strict local caches for repository git hooks.

These caches live under .git/aps-hook-cache and only speed up local hooks.
They are not quality gate proof and they are never written into evidence/.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from tools.long_gate_schema import content_equal, read_file_content

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
    "scripts/run_daily_quality_gate.py",
    "tools/git_hook_cache.py",
    "tools/git_hook_checks.py",
    "tools/test_registry.py",
)


class HookCacheError(RuntimeError):
    pass


def _run_git(args: Sequence[str]) -> str:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        detail = str(completed.stderr or completed.stdout or "git command failed").strip()
        raise HookCacheError(f"git {' '.join(args)} 失败：{detail}")
    return str(completed.stdout or "")


def _decode_nul_paths(output: str) -> List[str]:
    return [item for item in str(output or "").split("\0") if item]


def normalize_repo_path(path: str) -> str:
    text = str(path or "").replace("\\", "/").strip()
    if text.startswith("./"):
        text = text[2:]
    normalized = os.path.normpath(text).replace("\\", "/")
    if normalized in {"", "."}:
        return ""
    if normalized == ".." or normalized.startswith("../") or os.path.isabs(normalized):
        return ""
    return normalized


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
    for rel_path in sorted({normalize_repo_path(path) for path in paths}):
        if not rel_path:
            continue
        abs_path = REPO_ROOT / rel_path
        if abs_path.is_file():
            rows[rel_path] = read_file_content(str(abs_path))
        else:
            rows[rel_path] = None
    return rows


def _python_identity(executable: str) -> Dict[str, str]:
    realpath = os.path.realpath(str(executable or sys.executable))
    completed = subprocess.run(
        [realpath, "-c", "import sys; print(sys.version.replace('\\n', ' '))"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    version = str(completed.stdout or "").strip() if completed.returncode == 0 else ""
    return {"executable_realpath": realpath, "version": version}


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
    output = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    return [normalize_repo_path(path) for path in _decode_nul_paths(output) if normalize_repo_path(path)]


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

    temp_dir = tempfile.mkdtemp(prefix="aps-staged-ruff-")
    try:
        temp_root = Path(temp_dir)
        _export_index_to_temp(temp_root)
        command = [executable, "-m", "ruff", "check", "--force-exclude", "--", *list(targets)]
        print("[git-hook-cache] staged ruff:", " ".join(command), flush=True)
        returncode = subprocess.call(command, cwd=str(temp_root), env=_hook_env())
        if int(returncode) == 0:
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
