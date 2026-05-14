from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import quality_gate_shared
from tools.long_gate_schema import (
    LONG_GATE_CACHE_SCHEMA_VERSION,
    LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
    LONG_GATE_MANIFEST_SCHEMA_VERSION,
)
from tools.test_registry import (
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
    iter_startup_regressions,
)

LONG_GATE_SCHEMA_VERSION = LONG_GATE_MANIFEST_SCHEMA_VERSION

ENTRY_PYTEST_COLLECT_ALL = "pytest_collect_all"
ENTRY_FULL_TEST_DEBT = "full_test_debt"
ENTRY_RUFF_CHECK_FULL = "ruff_check_full"
ENTRY_PYRIGHT_GATE_FULL = "pyright_gate_full"
ENTRY_PYRIGHT_TOOLS_FULL = "pyright_tools_full"
ENTRY_ARCHITECTURE_FITNESS = "architecture_fitness"
ENTRY_REQUIRED_REGRESSIONS = "required_regressions"
ENTRY_DEBT_LEDGER_SYNC = "debt_ledger_sync"
ENTRY_STARTUP_RUNTIME_REGRESSIONS = "startup_runtime_regressions"
ENTRY_QUICKREF_VS_ROUTES = "quickref_vs_routes"
ENTRY_VERSION_OR_ENV_PROBE = "version_or_env_probe"
ENTRY_UNKNOWN = "unknown"

_VERSION_PROBE_ENTRY_IDS = {
    "python -m ruff --version": "ruff_version_probe",
    "python -m pyright --version": "pyright_version_probe",
    'python -c "import radon"': "radon_import_probe",
}

_LONG_ENTRY_TYPES = {
    ENTRY_PYTEST_COLLECT_ALL,
    ENTRY_FULL_TEST_DEBT,
    ENTRY_RUFF_CHECK_FULL,
    ENTRY_PYRIGHT_GATE_FULL,
    ENTRY_PYRIGHT_TOOLS_FULL,
    ENTRY_ARCHITECTURE_FITNESS,
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_DEBT_LEDGER_SYNC,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
    ENTRY_QUICKREF_VS_ROUTES,
}

_CACHE_ENABLED_ENTRY_TYPES = {
    ENTRY_PYTEST_COLLECT_ALL,
    ENTRY_FULL_TEST_DEBT,
    ENTRY_REQUIRED_REGRESSIONS,
    ENTRY_STARTUP_RUNTIME_REGRESSIONS,
}


def _stable_json_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _normalize_args(args: Iterable[Any]) -> List[str]:
    return [str(arg) for arg in list(args or [])]


def _normalize_command(command: Mapping[str, Any]) -> Dict[str, Any]:
    policy = str(command.get("output_policy") or "exact").strip().lower()
    if policy not in {"exact", "normalized"}:
        policy = "exact"
    return {
        "display": str(command.get("display") or "").strip(),
        "args": _normalize_args(command.get("args") or []),
        "capture_output": bool(command.get("capture_output")),
        "output_policy": policy,
    }


def _pytest_q_targets(args: Sequence[str]) -> Optional[List[str]]:
    normalized = _normalize_args(args)
    if len(normalized) < 4:
        return None
    if normalized[:4] != ["python", "-m", "pytest", "-q"]:
        return None
    return list(normalized[4:])


def _list_equal(left: Sequence[str], right: Sequence[str]) -> bool:
    return [str(item) for item in left] == [str(item) for item in right]


def _dedupe(items: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in list(items or []) if str(item)))


def classify_quality_gate_command(command: Mapping[str, Any]) -> str:
    normalized = _normalize_command(command)
    display = normalized["display"]
    args = normalized["args"]

    if display == "python -m pytest --collect-only -q tests":
        return ENTRY_PYTEST_COLLECT_ALL
    if display == "python tools/check_full_test_debt.py":
        return ENTRY_FULL_TEST_DEBT
    if display in _VERSION_PROBE_ENTRY_IDS:
        return ENTRY_VERSION_OR_ENV_PROBE
    if display == "python -m ruff check":
        return ENTRY_RUFF_CHECK_FULL
    if _list_equal(args[:5], ["python", "-m", "pyright", "-p", quality_gate_shared.QUALITY_GATE_PYRIGHT_GATE_CONFIG]):
        return ENTRY_PYRIGHT_GATE_FULL
    if _list_equal(args[:3], ["python", "-m", "pyright"]) and any(
        path in args for path in quality_gate_shared.QUALITY_GATE_TOOL_PATHS
    ):
        return ENTRY_PYRIGHT_TOOLS_FULL
    if display == "python -m pytest -q tests/test_architecture_fitness.py":
        return ENTRY_ARCHITECTURE_FITNESS
    if display == "python scripts/sync_debt_ledger.py check":
        return ENTRY_DEBT_LEDGER_SYNC
    if display == "python tests/check_quickref_vs_routes.py":
        return ENTRY_QUICKREF_VS_ROUTES

    pytest_targets = _pytest_q_targets(args)
    if pytest_targets is not None:
        if _list_equal(pytest_targets, quality_gate_shared.iter_quality_gate_required_tests()):
            return ENTRY_REQUIRED_REGRESSIONS
        if _list_equal(pytest_targets, iter_startup_regressions()):
            return ENTRY_STARTUP_RUNTIME_REGRESSIONS

    return ENTRY_UNKNOWN


def _classify_quality_gate_plan_command(command: Mapping[str, Any], *, index: int, debt_sync_index: Optional[int]) -> str:
    del index, debt_sync_index
    return classify_quality_gate_command(command)


def _entry_id_for_command(entry_type: str, command: Mapping[str, Any], index: int) -> str:
    display = str(command.get("display") or "").strip()
    if entry_type == ENTRY_VERSION_OR_ENV_PROBE:
        return _VERSION_PROBE_ENTRY_IDS.get(display, f"version_or_env_probe_{int(index):02d}")
    if entry_type == ENTRY_UNKNOWN:
        return f"unknown_{int(index):02d}"
    return entry_type


def _scopes_for_entry(
    entry_type: str,
    command: Optional[Mapping[str, Any]] = None,
) -> Tuple[List[str], List[str], List[str], List[str], List[str], List[str]]:
    input_scopes: List[str] = []
    config_scopes: List[str] = []
    tool_scopes: List[str] = []
    dependency_scopes: List[str] = []
    env_keys: List[str] = []
    output_files: List[str] = []

    if entry_type in _LONG_ENTRY_TYPES:
        tool_scopes = list(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)
        config_scopes = list(quality_gate_shared.QUALITY_GATE_SOURCE_FILES)

    if entry_type == ENTRY_PYRIGHT_TOOLS_FULL:
        input_scopes = list(quality_gate_shared.QUALITY_GATE_TOOL_PATHS)
    elif entry_type == ENTRY_PYTEST_COLLECT_ALL:
        input_scopes.extend(
            [
                "tests/**/*.py",
                "tests/**/conftest.py",
                "conftest.py",
                "core/**/*.py",
                "web/**/*.py",
                "data/**/*.py",
                "plugins/**/*.py",
                "scripts/**/*.py",
                "*.py",
                "app.py",
                "app_new_ui.py",
                "config.py",
                "schema.sql",
            ]
        )
        config_scopes.extend(
            [
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
                "tools/quality_gate_shared.py",
                "tools/test_debt_registry.py",
                "tools/test_registry.py",
                "scripts/run_quality_gate.py",
            ]
        )
        dependency_scopes.extend(
            [
                "requirements*.txt",
                "requirements-dev*.txt",
                "poetry.lock",
                "uv.lock",
                "Pipfile.lock",
            ]
        )
        env_keys.extend(
            [
                "python_executable_realpath",
                "python_version",
                "pytest_version",
                "pytest_plugin_distribution_versions",
                "platform",
                "PYTHONPATH",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "PYTEST_ADDOPTS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTEST_PLUGINS",
            ]
        )
        output_files = ["evidence/QualityGate/collect_nodeids.json"]
    elif entry_type == ENTRY_REQUIRED_REGRESSIONS:
        required_targets = _pytest_q_targets(_normalize_command(command or {}).get("args") or []) or []
        common_scope_policy = iter_required_regression_common_scope_policy()
        group_rows = iter_required_regression_groups()
        input_scopes = list(required_targets)
        input_scopes.extend(common_scope_policy.get("input_file_scopes") or [])
        config_scopes = list(common_scope_policy.get("config_file_scopes") or [])
        tool_scopes = list(common_scope_policy.get("tool_file_scopes") or [])
        dependency_scopes = list(common_scope_policy.get("dependency_file_scopes") or [])
        env_keys = list(common_scope_policy.get("env_keys") or [])
        for group in group_rows:
            input_scopes.extend(str(path) for path in list(group.get("input_file_scopes") or []))
            config_scopes.extend(str(path) for path in list(group.get("config_file_scopes") or []))
            tool_scopes.extend(str(path) for path in list(group.get("tool_file_scopes") or []))
            dependency_scopes.extend(str(path) for path in list(group.get("dependency_file_scopes") or []))
            env_keys.extend(str(key) for key in list(group.get("env_keys") or []))
        output_files.append(quality_gate_shared.QUALITY_GATE_REQUIRED_REGRESSIONS_REL.replace("\\", "/"))
    elif entry_type == ENTRY_STARTUP_RUNTIME_REGRESSIONS:
        input_scopes = list(iter_startup_regressions())
        input_scopes.extend(
            [
                "tests/conftest.py",
                "tests/main_style_regression_runner.py",
                "tests/runtime_cleanup_helper.py",
                "app.py",
                "app_new_ui.py",
                "config.py",
                "schema.sql",
                "web/bootstrap/**/*.py",
                "web/error_boundary.py",
                "web/error_handlers.py",
                "web/manual_src_security.py",
                "web/render_bridge.py",
                "web/routes/**/*.py",
                "web/ui_mode.py",
                "web/ui_mode_request.py",
                "web/ui_mode_store.py",
                "web/viewmodels/**/*.py",
                "core/**/*.py",
                "data/**/*.py",
                "plugins/**/*.py",
                "templates/**/*.html",
                "web_new_test/templates/**/*.html",
                "static/**/*",
                "web_new_test/static/**/*",
                "templates_excel/**/*",
                "assets/启动_排产系统_Chrome.bat",
                "build_win7*.bat",
                "installer/aps_win7*.iss",
                ".limcode/skills/aps-package-win7/scripts/package_win7.ps1",
            ]
        )
        config_scopes = [
            "pytest.ini",
            "pyproject.toml",
            "setup.cfg",
            "tox.ini",
            "tools/test_registry.py",
            "tools/quality_gate_shared.py",
            "tools/quality_gate_support.py",
        ]
        tool_scopes = [
            "scripts/run_quality_gate.py",
            "tools/long_gate_cache.py",
            "tools/long_gate_collect.py",
            "tools/long_gate_fingerprint.py",
            "tools/long_gate_full_test_debt.py",
            "tools/long_gate_manifest.py",
            "tools/long_gate_paths.py",
            "tools/long_gate_schema.py",
            "tools/long_gate_summary.py",
            "tools/test_registry.py",
            "tools/quality_gate_shared.py",
            "tools/quality_gate_support.py",
        ]
        dependency_scopes.extend(
            [
                "requirements*.txt",
                "requirements-dev*.txt",
                "poetry.lock",
                "uv.lock",
                "Pipfile.lock",
            ]
        )
        env_keys.extend(
            [
                "python_executable_realpath",
                "python_version",
                "pytest_version",
                "pytest_plugin_distribution_versions",
                "platform",
                "APS_ENV",
                "APS_DB_PATH",
                "APS_LOG_DIR",
                "APS_BACKUP_DIR",
                "APS_EXCEL_TEMPLATE_DIR",
                "APS_CHROME_PATH",
                "APS_HOST",
                "APS_PORT",
                "APS_SHARED_DATA_ROOT",
                "APS_STATIC_VERSION",
                "SECRET_KEY",
                "LOCALAPPDATA",
                "USERNAME",
                "USERDOMAIN",
                "COMPUTERNAME",
                "ProgramData",
                "PYTHONPATH",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "PYTEST_ADDOPTS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTEST_PLUGINS",
                "WERKZEUG_RUN_MAIN",
            ]
        )
        output_files = [
            quality_gate_shared.QUALITY_GATE_STARTUP_RUNTIME_REGRESSIONS_REL.replace("\\", "/"),
        ]
    elif entry_type == ENTRY_QUICKREF_VS_ROUTES:
        output_files = ["evidence/Conformance/quickref_vs_routes.md"]
    elif entry_type == ENTRY_FULL_TEST_DEBT:
        input_scopes.extend(
            [
                "tests/**/*.py",
                "tests/**/conftest.py",
                "conftest.py",
                "core/**/*.py",
                "web/**/*.py",
                "data/**/*.py",
                "plugins/**/*.py",
                "scripts/**/*.py",
                "desktop/**/*.py",
                "audit/**/*.py",
                "app.py",
                "app_new_ui.py",
                "check_manual_layout.py",
                "config.py",
                "schema.sql",
                "validate_dist_exe.py",
                "verify_manual_styles.py",
                "assets/**/*",
                "installer/**/*",
                "build_win7*.bat",
                "templates/**/*.html",
                "web_new_test/templates/**/*.html",
                "templates_excel/**/*",
                "static/**/*",
                "web_new_test/static/**/*",
                "audit/**/*.md",
                "docs/**/*.md",
                "evidence/README.md",
                "evidence/current/README.md",
                ".github/workflows/*.yml",
                ".gitignore",
                ".limcode/skills/**/*",
                ".limcode/plans/**/*",
                "开发文档/**/*.md",
                "evidence/QualityGate/collect_nodeids.json",
            ]
        )
        config_scopes.extend(
            [
                "pytest.ini",
                "pyproject.toml",
                "setup.cfg",
                "tox.ini",
                "开发文档/技术债务治理台账.md",
                "tools/check_full_test_debt.py",
                "tools/collect_full_test_debt.py",
                "tools/test_debt_registry.py",
                "tools/quality_gate_shared.py",
                "tools/quality_gate_support.py",
                "codestable/tools/**/*.py",
                "scripts/run_quality_gate.py",
            ]
        )
        dependency_scopes.extend(
            [
                "requirements*.txt",
                "requirements-dev*.txt",
                "poetry.lock",
                "uv.lock",
                "Pipfile.lock",
            ]
        )
        env_keys.extend(
            [
                "python_executable_realpath",
                "python_version",
                "pytest_version",
                "pytest_plugin_distribution_versions",
                "platform",
                "PYTHONPATH",
                "PYTHONUTF8",
                "PYTHONIOENCODING",
                "PYTEST_ADDOPTS",
                "PYTEST_DISABLE_PLUGIN_AUTOLOAD",
                "PYTEST_PLUGINS",
            ]
        )
        output_files = [
            quality_gate_shared.QUALITY_GATE_CURRENT_FULL_TEST_DEBT_REL.replace("\\", "/"),
            quality_gate_shared.QUALITY_GATE_FULL_TEST_DEBT_SUMMARY_REL.replace("\\", "/"),
            quality_gate_shared.QUALITY_GATE_FULL_TEST_DEBT_NODE_CACHE_REL.replace("\\", "/"),
        ]

    return (
        _dedupe(input_scopes),
        _dedupe(config_scopes),
        _dedupe(tool_scopes),
        _dedupe(dependency_scopes),
        _dedupe(env_keys),
        _dedupe(output_files),
    )


def _build_entry(command: Mapping[str, Any], index: int, *, entry_type: Optional[str] = None) -> Dict[str, Any]:
    normalized = _normalize_command(command)
    resolved_entry_type = entry_type or classify_quality_gate_command(normalized)
    input_scopes, config_scopes, tool_scopes, dependency_scopes, env_keys, output_files = _scopes_for_entry(
        resolved_entry_type,
        normalized,
    )
    command_hash = _stable_json_hash(normalized)
    long_gate_candidate = resolved_entry_type in _LONG_ENTRY_TYPES
    reuse_allowed = resolved_entry_type in _CACHE_ENABLED_ENTRY_TYPES
    entry = {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "cache_schema_version": LONG_GATE_CACHE_SCHEMA_VERSION,
        "fingerprint_schema_version": LONG_GATE_FINGERPRINT_SCHEMA_VERSION,
        "entry_id": _entry_id_for_command(resolved_entry_type, normalized, index),
        "entry_type": resolved_entry_type,
        "command_name": normalized["display"],
        "display": normalized["display"],
        "args": list(normalized["args"]),
        "capture_output": bool(normalized["capture_output"]),
        "output_policy": normalized["output_policy"],
        "command_hash": command_hash,
        "input_file_scopes": input_scopes,
        "config_file_scopes": config_scopes,
        "tool_file_scopes": tool_scopes,
        "dependency_file_scopes": dependency_scopes,
        "env_keys": env_keys,
        "output_result_files": output_files,
        "long_gate_candidate": long_gate_candidate,
        "cache_status": "enabled" if reuse_allowed else ("planned" if long_gate_candidate else "disabled"),
        "reuse_allowed": reuse_allowed,
        "force_invalidate_on": [],
        "fingerprint": None,
        "previous_success": None,
        "last_success_fingerprint": None,
    }
    return entry


def _git_head_sha(repo_root: str) -> str:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except Exception:
        return ""
    if int(proc.returncode) != 0:
        return ""
    return str(proc.stdout or "").strip()


def build_manifest_from_quality_gate_plan(
    command_plan: Sequence[Mapping[str, Any]],
    receipts: Optional[Sequence[Mapping[str, Any]]] = None,
    repo_root: Optional[str] = None,
) -> Dict[str, Any]:
    commands = [_normalize_command(command) for command in list(command_plan or [])]
    debt_sync_index = None
    for index, command in enumerate(commands, start=1):
        if classify_quality_gate_command(command) == ENTRY_DEBT_LEDGER_SYNC:
            debt_sync_index = index
            break
    manifest = {
        "schema_version": LONG_GATE_SCHEMA_VERSION,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "repo_root": os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT),
        "head_sha": _git_head_sha(os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)),
        "quality_gate_plan_hash": quality_gate_shared.hash_quality_gate_commands(commands),
        "entries": [
            _build_entry(
                command,
                index,
                entry_type=_classify_quality_gate_plan_command(
                    command,
                    index=index,
                    debt_sync_index=debt_sync_index,
                ),
            )
            for index, command in enumerate(commands, start=1)
        ],
        "warnings": [],
    }
    if receipts is not None:
        _attach_receipt_observations(manifest, receipts)
    return manifest


def build_long_gate_manifest(repo_root: Optional[str] = None) -> Dict[str, Any]:
    root = os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    return build_manifest_from_quality_gate_plan(command_plan, repo_root=root)


def _load_json_file(path: str) -> Tuple[Optional[Dict[str, Any]], str]:
    try:
        with open(path, encoding="utf-8") as handle:
            loaded = json.load(handle)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    except OSError as exc:
        return None, f"unreadable: {exc}"
    if not isinstance(loaded, dict):
        return None, "top-level value is not an object"
    return loaded, ""


def _coerce_int(value: Any, *, field: str, warnings: List[str]) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        warnings.append(f"invalid numeric field: {field}={value!r}")
        return 0


def _coerce_float(value: Any, *, field: str, warnings: List[str]) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        if value is not None:
            warnings.append(f"invalid numeric field: {field}={value!r}")
        return None


def load_local_quality_gate_receipts(repo_root: Optional[str] = None) -> List[Dict[str, Any]]:
    root = os.path.abspath(repo_root or quality_gate_shared.REPO_ROOT)
    receipts_dir = os.path.join(root, quality_gate_shared.QUALITY_GATE_RECEIPTS_DIR_REL.replace("/", os.sep))
    rows: List[Dict[str, Any]] = []
    for abs_path in sorted(glob.glob(os.path.join(receipts_dir, "*.json"))):
        rel_path = os.path.relpath(abs_path, root).replace("\\", "/")
        payload, error = _load_json_file(abs_path)
        warnings: List[str] = []
        row: Dict[str, Any] = {"path": rel_path}
        if error:
            row.update({"load_error": error, "display": "", "command_index": 0, "duration_unknown": True, "warnings": warnings})
        else:
            payload = payload or {}
            duration_s = _coerce_float(payload.get("duration_s"), field="duration_s", warnings=warnings)
            row.update(
                {
                    "display": str(payload.get("display") or "").strip(),
                    "command_index": _coerce_int(payload.get("command_index"), field="command_index", warnings=warnings),
                    "returncode": _coerce_int(payload.get("returncode"), field="returncode", warnings=warnings),
                    "duration_s": duration_s,
                    "duration_unknown": duration_s is None,
                    "duration_kind": str(payload.get("duration_kind") or "").strip(),
                    "original_duration_s": _coerce_float(
                        payload.get("original_duration_s"),
                        field="original_duration_s",
                        warnings=warnings,
                    ),
                    "execution_mode": str(payload.get("execution_mode") or "executed").strip() or "executed",
                    "warnings": warnings,
                }
            )
        rows.append(row)
    return rows


def _attach_receipt_observations(manifest: Dict[str, Any], receipts: Sequence[Mapping[str, Any]]) -> None:
    entries_by_display = {str(entry.get("display") or ""): entry for entry in list(manifest.get("entries") or [])}
    for receipt in list(receipts or []):
        display = str(receipt.get("display") or "").strip()
        if not display:
            manifest.setdefault("warnings", []).append(
                f"receipt unreadable or missing display: {receipt.get('path', '')}"
            )
            continue
        entry = entries_by_display.get(display)
        if entry is None:
            manifest.setdefault("warnings", []).append(f"local receipt command is not in current plan: {display}")
            continue
        entry.setdefault("local_receipts", []).append(dict(receipt))


def _entry_label(entry: Mapping[str, Any]) -> str:
    if str(entry.get("entry_type") or "") == ENTRY_UNKNOWN:
        return "UNKNOWN"
    if bool(entry.get("reuse_allowed")):
        return "CACHE-ENABLED"
    if bool(entry.get("long_gate_candidate")):
        return "LONG-CANDIDATE"
    return "PROBE"


def _format_receipt_line(receipt: Mapping[str, Any]) -> str:
    path = str(receipt.get("path") or "")
    if receipt.get("duration_unknown"):
        duration = "duration_unknown"
    else:
        duration = f"{float(receipt.get('duration_s') or 0.0):.3f}s"
    duration_kind = str(receipt.get("duration_kind") or "").strip()
    original_duration = receipt.get("original_duration_s")
    if duration_kind and original_duration is not None:
        duration = f"{duration}, kind={duration_kind}, original={float(original_duration):.3f}s"
    return f"    receipt: {path} ({duration})"


def _format_receipt_warnings(receipt: Mapping[str, Any]) -> List[str]:
    return [f"    warning: {item}" for item in list(receipt.get("warnings") or [])]


def print_long_gate_manifest(manifest: Mapping[str, Any], *, include_local_receipts: bool = False) -> None:
    entries = list(manifest.get("entries") or [])
    print("Long gate manifest")
    print(f"schema_version: {manifest.get('schema_version')}")
    print(f"head_sha: {manifest.get('head_sha') or 'unknown'}")
    print(f"commands: {len(entries)}")
    print("")
    for index, entry in enumerate(entries, start=1):
        print(f"{index:02d}. [{_entry_label(entry)}] {entry.get('entry_id', '')}: {entry.get('display', '')}")
        if include_local_receipts:
            for receipt in list(entry.get("local_receipts") or []):
                print(_format_receipt_line(receipt))
                for warning in _format_receipt_warnings(receipt):
                    print(warning)
    if include_local_receipts:
        has_receipts = any(entry.get("local_receipts") for entry in entries)
        warnings = [str(item) for item in list(manifest.get("warnings") or [])]
        if not has_receipts and not warnings:
            print("")
            print(
                "No local QualityGate receipts found. Slow-command ranking unavailable; "
                "using command-plan based long-gate candidates."
            )
        if warnings:
            print("")
            print("Warnings")
            for warning in warnings:
                print(f"- {warning}")


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print the long-gate manifest derived from the real QualityGate plan.")
    parser.add_argument("--print", dest="print_manifest", action="store_true", help="print the current long-gate manifest")
    parser.add_argument(
        "--include-local-receipts",
        action="store_true",
        help="read local evidence/QualityGate receipts and include duration hints when available",
    )
    parser.add_argument("--repo-root", default=quality_gate_shared.REPO_ROOT, help="repository root to inspect")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    if not bool(args.print_manifest):
        args.print_manifest = True
    receipts = load_local_quality_gate_receipts(args.repo_root) if bool(args.include_local_receipts) else None
    command_plan = quality_gate_shared.build_quality_gate_command_plan()
    manifest = build_manifest_from_quality_gate_plan(command_plan, receipts=receipts, repo_root=args.repo_root)
    print_long_gate_manifest(manifest, include_local_receipts=bool(args.include_local_receipts))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
