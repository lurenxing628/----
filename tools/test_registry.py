from __future__ import annotations

import hashlib
import json
import os
import subprocess
from typing import Any, Dict, List, Mapping, Optional, Sequence

from tools.test_registry_data import (
    QUALITY_GATE_GUARD_TESTS,
    QUALITY_GATE_REQUIRED_TESTS,
    QUALITY_GATE_SELFTEST_PATH,
    QUALITY_GATE_STARTUP_REGRESSION_ARGS,
    REPO_ROOT,
    REQUIRED_REGRESSION_COMMON_SCOPES,
    TEST_ONLY_HELPER_IMPACT,
)
from tools.test_registry_groups_misc import MISC_REQUIRED_REGRESSION_GROUPS
from tools.test_registry_groups_scheduler import SCHEDULER_REQUIRED_REGRESSION_GROUPS

REQUIRED_REGRESSION_GROUPS = (
    *SCHEDULER_REQUIRED_REGRESSION_GROUPS,
    *MISC_REQUIRED_REGRESSION_GROUPS,
)

def _normalize_registry_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/")


def _normalize_scope_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_path in list(paths or []):
        normalized = _normalize_registry_path(str(raw_path))
        if not normalized or normalized in seen:
            continue
        if os.path.isabs(normalized):
            raise ValueError("required regression scope path must be repo-relative: " + normalized)
        if "\0" in normalized:
            raise ValueError("required regression scope path contains NUL: " + normalized)
        seen.add(normalized)
        out.append(normalized)
    return out


def _normalize_env_keys(keys: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_key in list(keys or []):
        key = str(raw_key or "").strip()
        if not key or key in seen:
            continue
        if "\0" in key:
            raise ValueError("required regression env key contains NUL: " + key)
        seen.add(key)
        out.append(key)
    return out


def _is_top_level_test_only_helper_path(path: str) -> bool:
    normalized = _normalize_registry_path(path)
    name = os.path.basename(normalized)
    return (
        normalized.startswith("tests/")
        and normalized.count("/") == 1
        and normalized.endswith(".py")
        and name.endswith("_helpers.py")
        and name != "conftest.py"
    )


def _is_regular_helper_impact_target(path: str) -> bool:
    normalized = _normalize_registry_path(path)
    name = os.path.basename(normalized)
    if normalized == "conftest.py" or normalized.endswith("/conftest.py"):
        return False
    if not normalized.startswith("tests/") or normalized.count("/") != 1 or not normalized.endswith(".py"):
        return False
    if name.endswith("_helpers.py"):
        return False
    return name.startswith("test_") or name.startswith("regression_")


def iter_test_only_helper_impacts(
    helper_impacts: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[str]]:
    impacts = helper_impacts if helper_impacts is not None else TEST_ONLY_HELPER_IMPACT
    rows: Dict[str, List[str]] = {}
    for helper_path, target_paths in sorted(impacts.items()):
        helper = _normalize_registry_path(helper_path)
        if not _is_top_level_test_only_helper_path(helper):
            raise ValueError("test-only helper impact helper must be top-level tests/*_helpers.py: " + helper)
        targets = normalize_test_paths(list(target_paths or []))
        if not targets:
            raise ValueError("test-only helper impact targets are empty: " + helper)
        for target in targets:
            if not _is_regular_helper_impact_target(target):
                raise ValueError("test-only helper impact target must be a top-level test file: " + target)
        rows[helper] = targets
    return rows


def test_only_helper_impacts_for_path(
    path: str,
    helper_impacts: Optional[Mapping[str, Sequence[str]]] = None,
) -> List[str]:
    normalized = _normalize_registry_path(path)
    return list(iter_test_only_helper_impacts(helper_impacts).get(normalized) or [])


def normalize_test_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for rel_path in list(paths or []):
        normalized = str(rel_path or "").strip().replace("\\", "/")
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        out.append(normalized)
    return out


def iter_required_tests(required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> List[str]:
    return normalize_test_paths(required_tests)


def iter_startup_regressions(
    startup_regressions: Sequence[str] = QUALITY_GATE_STARTUP_REGRESSION_ARGS,
) -> List[str]:
    return normalize_test_paths(startup_regressions)


def iter_non_regression_guard_tests(required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> List[str]:
    out: List[str] = []
    for rel_path in iter_required_tests(required_tests):
        if os.path.basename(rel_path).startswith("regression_"):
            continue
        out.append(rel_path)
    return out


def required_test_nodeid_matches(nodeid: str, required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> bool:
    normalized_nodeid = str(nodeid or "").strip().replace("\\", "/")
    node_path = normalized_nodeid.split("::", 1)[0]
    return any(
        node_path == required_path or normalized_nodeid.startswith(required_path + "::")
        for required_path in iter_required_tests(required_tests)
    )


def build_test_path_status(
    paths: Sequence[str],
    *,
    repo_root: Optional[str] = None,
) -> List[Dict[str, Any]]:
    root = os.path.abspath(repo_root or REPO_ROOT)
    rows: List[Dict[str, Any]] = []
    for rel_path in normalize_test_paths(paths):
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        rows.append(
            {
                "path": rel_path,
                "exists": os.path.exists(os.path.join(root, rel_path)),
                "tracked": tracked.returncode == 0,
            }
        )
    return rows


def stable_registry_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_required_tests_registry(required_tests: Sequence[str]) -> str:
    return stable_registry_hash(iter_required_tests(required_tests))


def iter_required_regression_groups(
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    source = REQUIRED_REGRESSION_GROUPS if groups is None else groups
    rows: List[Dict[str, Any]] = []
    seen_group_ids = set()
    for raw_group in list(source or []):
        group_id = str(raw_group.get("group_id") or "").strip()
        if not group_id:
            raise ValueError("required regression group_id is empty")
        if group_id in seen_group_ids:
            raise ValueError("required regression group_id is duplicated: " + group_id)
        seen_group_ids.add(group_id)
        target_paths = normalize_test_paths(list(raw_group.get("target_paths") or []))
        if not target_paths:
            raise ValueError("required regression group targets are empty: " + group_id)
        rows.append(
            {
                "group_id": group_id,
                "label": str(raw_group.get("label") or group_id).strip() or group_id,
                "target_paths": target_paths,
                "input_file_scopes": _normalize_scope_paths(raw_group.get("input_file_scopes") or ()),
                "config_file_scopes": _normalize_scope_paths(raw_group.get("config_file_scopes") or ()),
                "tool_file_scopes": _normalize_scope_paths(raw_group.get("tool_file_scopes") or ()),
                "dependency_file_scopes": _normalize_scope_paths(raw_group.get("dependency_file_scopes") or ()),
                "env_keys": _normalize_env_keys(raw_group.get("env_keys") or ()),
            }
        )
    return rows


def iter_required_regression_common_scope_policy(
    scopes: Optional[Mapping[str, Sequence[str]]] = None,
) -> Dict[str, List[str]]:
    source = REQUIRED_REGRESSION_COMMON_SCOPES if scopes is None else scopes
    return {
        "input_file_scopes": _normalize_scope_paths(source.get("input_file_scopes") or ()),
        "config_file_scopes": _normalize_scope_paths(source.get("config_file_scopes") or ()),
        "tool_file_scopes": _normalize_scope_paths(source.get("tool_file_scopes") or ()),
        "dependency_file_scopes": _normalize_scope_paths(source.get("dependency_file_scopes") or ()),
        "env_keys": _normalize_env_keys(source.get("env_keys") or ()),
    }


def hash_required_regression_groups(
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> str:
    return stable_registry_hash(iter_required_regression_groups(groups))


def validate_required_regression_group_coverage(
    required_tests: Sequence[str],
    groups: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    required_paths = iter_required_tests(required_tests)
    required_set = set(required_paths)
    group_rows = iter_required_regression_groups(groups)
    flat_targets: List[str] = []
    target_to_groups: Dict[str, List[str]] = {}
    for group in group_rows:
        group_id = str(group.get("group_id") or "")
        for target in list(group.get("target_paths") or []):
            normalized = _normalize_registry_path(str(target))
            flat_targets.append(normalized)
            target_to_groups.setdefault(normalized, []).append(group_id)

    duplicates = []
    for target, owning_groups in sorted(target_to_groups.items()):
        if len(owning_groups) > 1 or flat_targets.count(target) > 1:
            duplicates.append(
                {
                    "path": target,
                    "groups": list(owning_groups),
                }
            )

    missing = [path for path in required_paths if path not in target_to_groups]
    unknown = [path for path in flat_targets if path not in required_set]
    return {
        "missing": missing,
        "duplicates": duplicates,
        "unknown": sorted(dict.fromkeys(unknown)),
        "required_target_count": len(required_paths),
        "group_target_count": len(flat_targets),
        "group_count": len(group_rows),
        "required_registry_hash": hash_required_tests_registry(required_paths),
        "group_registry_hash": hash_required_regression_groups(group_rows),
    }


def hash_test_registry(
    *,
    required_tests: Optional[Sequence[str]] = None,
    startup_regressions: Optional[Sequence[str]] = None,
    active_xfail_entries: Optional[Sequence[Dict[str, Any]]] = None,
) -> str:
    active_entries = []
    for entry in list(active_xfail_entries or []):
        active_entries.append(
            {
                "debt_id": str(entry.get("debt_id") or ""),
                "nodeid": str(entry.get("nodeid") or ""),
                "reason": str(entry.get("reason") or ""),
            }
        )
    active_entries.sort(key=lambda item: (item["nodeid"], item["debt_id"]))
    required_source = QUALITY_GATE_REQUIRED_TESTS if required_tests is None else required_tests
    startup_source = QUALITY_GATE_STARTUP_REGRESSION_ARGS if startup_regressions is None else startup_regressions
    return stable_registry_hash(
        {
            "required_tests": iter_required_tests(required_source),
            "startup_regressions": iter_startup_regressions(startup_source),
            "active_xfail_entries": active_entries,
        }
    )


__all__ = [
    "QUALITY_GATE_GUARD_TESTS",
    "QUALITY_GATE_REQUIRED_TESTS",
    "QUALITY_GATE_SELFTEST_PATH",
    "QUALITY_GATE_STARTUP_REGRESSION_ARGS",
    "REQUIRED_REGRESSION_COMMON_SCOPES",
    "REQUIRED_REGRESSION_GROUPS",
    "TEST_ONLY_HELPER_IMPACT",
    "build_test_path_status",
    "hash_required_regression_groups",
    "hash_required_tests_registry",
    "hash_test_registry",
    "iter_non_regression_guard_tests",
    "iter_required_regression_common_scope_policy",
    "iter_required_regression_groups",
    "iter_required_tests",
    "iter_startup_regressions",
    "iter_test_only_helper_impacts",
    "normalize_test_paths",
    "required_test_nodeid_matches",
    "stable_registry_hash",
    "test_only_helper_impacts_for_path",
    "validate_required_regression_group_coverage",
]
