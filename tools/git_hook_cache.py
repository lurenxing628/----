#!/usr/bin/env python3
"""Strict local caches for repository git hooks.

These caches live under .git/aps-hook-cache and only speed up local hooks.
They are not quality gate proof and they are never written into evidence/.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
CACHE_SCHEMA_VERSION = 1
STAGED_RUFF_CACHE_NAME = "staged-ruff.json"
PRE_PUSH_DAILY_CACHE_NAME = "pre-push-daily.json"
FINAL_GATE_PASS_CACHE_NAME = "final-gate-pass.json"

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
FINAL_GATE_SOURCE_PATHS = (
    ".pre-commit-config.yaml",
    "scripts/run_quality_gate.py",
    "tools/git_hook_cache.py",
    "tools/git_hook_checks.py",
    "tools/quality_gate_shared.py",
    "tools/quality_gate_support.py",
    "tools/long_gate_cache.py",
    "tools/long_gate_fingerprint.py",
    "tools/long_gate_manifest.py",
    "tools/long_gate_summary.py",
)
FINAL_GATE_ARTIFACT_PATHS = (
    "evidence/QualityGate/quality_gate_manifest.json",
    "evidence/QualityGate/long_gate/summary.json",
    "evidence/QualityGate/long_gate/summary.md",
    "evidence/QualityGate/receipts",
    "evidence/QualityGate/logs",
)


class HookCacheError(RuntimeError):
    pass


def _run_git(args: Sequence[str], *, text: bool = True) -> str:
    completed = subprocess.run(
        ["git", *list(args)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=text,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
        check=False,
    )
    if completed.returncode != 0:
        stderr = completed.stderr if text else bytes(completed.stderr or b"").decode("utf-8", errors="replace")
        stdout = completed.stdout if text else bytes(completed.stdout or b"").decode("utf-8", errors="replace")
        detail = str(stderr or stdout or "git command failed").strip()
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


def _sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(65536)
            if not chunk:
                break
            hasher.update(chunk)
    return hasher.hexdigest()


def _file_hashes(paths: Iterable[str]) -> Dict[str, str]:
    rows: Dict[str, str] = {}
    for rel_path in sorted({normalize_repo_path(path) for path in paths}):
        if not rel_path:
            continue
        abs_path = REPO_ROOT / rel_path
        if abs_path.is_file():
            rows[rel_path] = _sha256_file(abs_path)
        else:
            rows[rel_path] = "<missing>"
    return rows


def _stable_hash(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(payload), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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


def head_sha() -> str:
    return _run_git(["rev-parse", "HEAD"]).strip()


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
        "watched_files": _file_hashes(watched_paths),
    }


def _cache_matches(path: Path, key_hash: str) -> bool:
    payload = _load_json(path)
    return bool(payload and payload.get("status") == "passed" and payload.get("key_hash") == key_hash)


def _write_pass_cache(path: Path, *, key_hash: str, key_payload: Mapping[str, Any], extra: Mapping[str, Any]) -> None:
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "status": "passed",
        "key_hash": key_hash,
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
    key_hash = _stable_hash(key_payload)
    path = cache_path(STAGED_RUFF_CACHE_NAME)
    if _cache_matches(path, key_hash):
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
                key_hash=key_hash,
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


def daily_gate_cache_key(executable: str, *, remote_name: str = "", remote_ref: str = "") -> Tuple[str, Dict[str, Any]]:
    key_payload = _cache_key_payload(
        kind="pre-push-daily",
        executable=executable,
        watched_paths=DAILY_GATE_TOOL_PATHS,
        tool_modules=("ruff", "pytest", "pyright"),
        extra={
            "head_sha": head_sha(),
            "head_tree": head_tree_hash(),
            "git_status_short": git_status_lines(),
            "remote_name": str(remote_name or ""),
            "remote_ref": str(remote_ref or ""),
        },
    )
    return _stable_hash(key_payload), key_payload


def pre_push_daily_cache_hit(executable: str, *, remote_name: str = "", remote_ref: str = "") -> bool:
    if git_status_lines():
        return False
    key_hash, _payload = daily_gate_cache_key(executable, remote_name=remote_name, remote_ref=remote_ref)
    return _cache_matches(cache_path(PRE_PUSH_DAILY_CACHE_NAME), key_hash)


def write_pre_push_daily_cache(executable: str, *, remote_name: str = "", remote_ref: str = "") -> None:
    if git_status_lines():
        raise HookCacheError("pre-push daily gate pass cache 只能在干净工作区写入")
    key_hash, key_payload = daily_gate_cache_key(executable, remote_name=remote_name, remote_ref=remote_ref)
    _write_pass_cache(
        cache_path(PRE_PUSH_DAILY_CACHE_NAME),
        key_hash=key_hash,
        key_payload=key_payload,
        extra={
            "head_sha": key_payload["extra"]["head_sha"],
            "head_tree": key_payload["extra"]["head_tree"],
            "remote_name": str(remote_name or ""),
            "remote_ref": str(remote_ref or ""),
        },
    )


def _hash_path(rel_path: str) -> Dict[str, Any]:
    normalized = normalize_repo_path(rel_path)
    abs_path = REPO_ROOT / normalized
    if abs_path.is_file():
        return {"kind": "file", "path": normalized, "sha256": _sha256_file(abs_path)}
    if abs_path.is_dir():
        rows = []
        for root, dirs, files in os.walk(str(abs_path)):
            dirs.sort()
            files.sort()
            for filename in files:
                file_path = Path(root) / filename
                rel_file = normalize_repo_path(str(file_path.relative_to(REPO_ROOT)))
                rows.append({"path": rel_file, "sha256": _sha256_file(file_path)})
        return {"kind": "directory", "path": normalized, "files": rows, "hash": _stable_hash({"files": rows})}
    return {"kind": "missing", "path": normalized}


def final_gate_artifact_fingerprints() -> List[Dict[str, Any]]:
    return [_hash_path(path) for path in FINAL_GATE_ARTIFACT_PATHS]


def final_gate_cache_key(executable: str) -> Tuple[str, Dict[str, Any]]:
    artifacts = final_gate_artifact_fingerprints()
    key_payload = _cache_key_payload(
        kind="final-gate-exact-head",
        executable=executable,
        watched_paths=FINAL_GATE_SOURCE_PATHS,
        tool_modules=("ruff", "pytest", "pyright"),
        extra={
            "head_sha": head_sha(),
            "head_tree": head_tree_hash(),
            "git_status_short": git_status_lines(),
            "artifacts": artifacts,
        },
    )
    return _stable_hash(key_payload), key_payload


def final_gate_cache_hit(executable: str) -> bool:
    if git_status_lines():
        return False
    key_hash, _payload = final_gate_cache_key(executable)
    return _cache_matches(cache_path(FINAL_GATE_PASS_CACHE_NAME), key_hash)


def write_final_gate_cache(executable: str) -> None:
    if git_status_lines():
        raise HookCacheError("final gate pass cache 只能在干净工作区写入")
    key_hash, key_payload = final_gate_cache_key(executable)
    _write_pass_cache(
        cache_path(FINAL_GATE_PASS_CACHE_NAME),
        key_hash=key_hash,
        key_payload=key_payload,
        extra={
            "head_sha": key_payload["extra"]["head_sha"],
            "head_tree": key_payload["extra"]["head_tree"],
        },
    )
