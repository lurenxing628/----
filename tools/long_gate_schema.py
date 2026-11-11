from __future__ import annotations

import base64
import json
import math
import os
import subprocess
from typing import Any, Dict, List, Mapping, Sequence

from tools.long_gate_paths import LONG_GATE_CACHE_DIR_REL, real_repo_root

LONG_GATE_CACHE_SCHEMA_VERSION = 2
LONG_GATE_FINGERPRINT_SCHEMA_VERSION = 2
FULL_TEST_DEBT_NODE_CACHE_SCHEMA_VERSION = 2
LONG_GATE_MANIFEST_SCHEMA_VERSION = 2
LONG_GATE_SUMMARY_SCHEMA_VERSION = 2

LONG_GATE_RUNNER_VERSION_PATHS = ("scripts/run_quality_gate.py",)
LONG_GATE_TOOLING_VERSION_PATHS = (
    "tools/long_gate_cache.py",
    "tools/long_gate_collect.py",
    "tools/long_gate_fingerprint.py",
    "tools/long_gate_manifest.py",
    "tools/long_gate_paths.py",
    "tools/long_gate_schema.py",
    "tools/long_gate_summary.py",
)


def canonical_content(payload: Any) -> str:
    """Return the complete canonical JSON content used by gate comparisons."""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


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
        "PYTHONHASHSEED",
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
PRIVATE_ENVIRONMENT_KEYS = frozenset({"SECRET_KEY"})
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
SENSITIVE_SOURCE_BASENAMES = frozenset({"aps_secret_key.txt", "aps_runtime.json"})


def private_environment_value(source: Mapping[str, str], key: str) -> str:
    return str(source.get(key) or "").strip()


def decode_nul_paths(output: bytes) -> List[str]:
    return [raw.decode("utf-8", errors="replace") for raw in bytes(output or b"").split(b"\0") if raw]


class SensitiveSourceError(ValueError):
    """A source holds credentials, so its content must not enter cache or proof payloads."""


def read_file_content(path: str) -> str:
    """Return original bytes reversibly; credentials stay in their existing owner."""
    if os.path.basename(os.path.realpath(path)).lower() in SENSITIVE_SOURCE_BASENAMES:
        raise SensitiveSourceError(f"source is a credential-bearing runtime file: {path}")
    with open(path, "rb") as handle:
        data = handle.read()
    for key in sorted(PRIVATE_ENVIRONMENT_KEYS):
        value = private_environment_value(os.environ, key)
        if value and os.fsencode(value) in data:
            raise SensitiveSourceError(f"source contains sensitive environment value for {key}: {path}")
    return base64.b64encode(data).decode("ascii")


def _validate_json_value(value: Any) -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            raise ValueError(f"Out of range float values are not JSON compliant: {value!r}")
        return
    if isinstance(value, (list, tuple)):
        for item in value:
            _validate_json_value(item)
        return
    if isinstance(value, dict):
        if not all(type(key) is str for key in value):
            canonical_content(value)
            return
        for item in value.values():
            _validate_json_value(item)
        return
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _validated_content_equal(left: Any, right: Any) -> bool:
    if left is right:
        return True
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, int):
        return isinstance(right, int) and not isinstance(right, bool) and left == right
    if isinstance(left, float):
        if not isinstance(right, float):
            return False
        if left == 0.0 and right == 0.0:
            return math.copysign(1.0, left) == math.copysign(1.0, right)
        return left == right
    if isinstance(left, str):
        return isinstance(right, str) and left == right
    if isinstance(left, (list, tuple)):
        if not isinstance(right, (list, tuple)) or len(left) != len(right):
            return False
        return all(_validated_content_equal(l_item, r_item) for l_item, r_item in zip(left, right))
    if isinstance(left, dict):
        if not isinstance(right, dict):
            return False
        if not (all(type(key) is str for key in left) and all(type(key) is str for key in right)):
            return canonical_content(left) == canonical_content(right)
        if len(left) != len(right) or left.keys() != right.keys():
            return False
        return all(_validated_content_equal(left[key], right[key]) for key in left)
    return False


def content_equal(left: Any, right: Any) -> bool:
    _validate_json_value(left)
    _validate_json_value(right)
    return _validated_content_equal(left, right)


def _path_version_row(repo_root: str, rel_path: str) -> Dict[str, Any]:
    root = real_repo_root(repo_root)
    normalized = str(rel_path or "").replace("\\", "/")
    abs_path = (
        os.path.abspath(normalized)
        if os.path.isabs(normalized)
        else os.path.join(root, normalized.replace("/", os.sep))
    )
    real_path = os.path.realpath(abs_path)
    target_inside_repo = real_path == root or real_path.startswith(root + os.sep)
    if not target_inside_repo and not os.path.islink(abs_path):
        return {
            "path": normalized,
            "exists": os.path.lexists(abs_path),
            "kind": "outside_repo",
            "target_inside_repo": False,
        }
    if not os.path.lexists(abs_path):
        return {"path": normalized, "exists": False, "kind": "missing"}
    if os.path.islink(abs_path):
        return {
            "path": normalized,
            "exists": True,
            "kind": "symlink",
            "target": os.readlink(abs_path),
            "target_content_base64": read_file_content(real_path)
            if target_inside_repo and os.path.isfile(real_path)
            else "",
            "target_realpath": real_path,
            "target_inside_repo": target_inside_repo,
        }
    if os.path.isfile(abs_path):
        return {"path": normalized, "exists": True, "kind": "file", "content_base64": read_file_content(abs_path)}
    return {"path": normalized, "exists": True, "kind": "directory" if os.path.isdir(abs_path) else "other"}


def version_rows_for_paths(repo_root: str, rel_paths: Sequence[str]) -> List[Dict[str, Any]]:
    return [_path_version_row(repo_root, str(path)) for path in list(rel_paths or [])]


def version_info_for_paths(repo_root: str, rel_paths: Sequence[str]) -> Dict[str, Any]:
    rows = version_rows_for_paths(repo_root, rel_paths)
    untrusted = [
        str(row.get("path") or "")
        for row in rows
        if row.get("kind") == "outside_repo"
        or (row.get("kind") == "symlink" and not bool(row.get("target_inside_repo")))
    ]
    return {"rows": rows, "untrusted_paths": untrusted}


def _git_rev_parse_path(repo_root: str, *args: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"git rev-parse {' '.join(args)} failed in {repo_root}: {exc}") from exc
    raw_value = str(proc.stdout or "").strip()
    if int(proc.returncode) == 0 and raw_value:
        path_text = raw_value
        if not os.path.isabs(path_text):
            path_text = os.path.join(repo_root, path_text)
        return os.path.realpath(path_text)
    detail = str(proc.stderr or proc.stdout or "").strip() or "git rev-parse failed"
    raise RuntimeError(f"git rev-parse {' '.join(args)} failed in {repo_root}: {detail}")


def repo_identity(repo_root: str) -> Dict[str, str]:
    root = real_repo_root(repo_root)
    return {
        "checkout_root_realpath": _git_rev_parse_path(root, "--show-toplevel"),
        "git_common_dir_realpath": _git_rev_parse_path(root, "--git-common-dir"),
    }


def long_gate_repo_identity(repo_root: str) -> Dict[str, str]:
    identity = repo_identity(repo_root)
    return {
        "repo_root_realpath": identity["checkout_root_realpath"],
        "git_common_dir_realpath": identity["git_common_dir_realpath"],
    }


def long_gate_cache_metadata(repo_root: str, *, cache_dir: str = LONG_GATE_CACHE_DIR_REL) -> Dict[str, Any]:
    root = real_repo_root(repo_root)
    runner = version_info_for_paths(root, LONG_GATE_RUNNER_VERSION_PATHS)
    tooling = version_info_for_paths(root, LONG_GATE_TOOLING_VERSION_PATHS)
    metadata: Dict[str, Any] = {
        "cache_schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        "fingerprint_schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "runner_version_content": runner["rows"],
        "tooling_version_content": tooling["rows"],
        "runner_version_untrusted_paths": runner["untrusted_paths"],
        "tooling_version_untrusted_paths": tooling["untrusted_paths"],
        "cache_dir": str(cache_dir or LONG_GATE_CACHE_DIR_REL).replace("\\", "/"),
    }
    metadata.update(long_gate_repo_identity(root))
    return metadata
