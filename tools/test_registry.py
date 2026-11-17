from __future__ import annotations

import fnmatch
import os
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from tools.path_roles import PRODUCTION, ROOT_FILE_SCOPE_PREFIX, matches_root_file, role_roots
from tools.test_registry_data import (
    QUALITY_GATE_REQUIRED_TESTS,
    QUALITY_GATE_STARTUP_REGRESSION_ARGS,
    REQUIRED_REGRESSION_COMMON_SCOPES,
    REQUIRED_REGRESSION_GROUPS,
    RegistryGroup,
)

# 生产源文件 = 生产角色的 Python 根（取自 tools/path_roles.py）+ 随包交付的前端应用、模板、静态资源与 schema.sql。
# 各根下所有源码后缀的文件都要被 required 作用域覆盖；随包交付的第三方 vendor 资源同样计入
# （路径角色为 Python 引用分析跳过 vendor 目录，这里不跳过）。
PRODUCTION_SOURCE_ROOTS = (
    *role_roots((PRODUCTION,)),
    "frontend/workbench/app",
    "templates",
    "static",
    "schema.sql",
)
PRODUCTION_SOURCE_EXTENSIONS = (".py", ".js", ".jsx", ".cjs", ".css", ".html", ".sql")
_SCOPE_KEYS = ("input_file_scopes", "config_file_scopes", "tool_file_scopes", "dependency_file_scopes")
_SKIP_DIR_NAMES = frozenset({"__pycache__", "node_modules", ".git"})


def _normalize_registry_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def _normalize_scope_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_path in paths:
        normalized = _normalize_registry_path(raw_path)
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
    for raw_key in keys:
        key = raw_key.strip()
        if not key or key in seen:
            continue
        if "\0" in key:
            raise ValueError("required regression env key contains NUL: " + key)
        seen.add(key)
        out.append(key)
    return out


def normalize_test_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for rel_path in paths:
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


def required_test_nodeid_matches(nodeid: str, required_tests: Sequence[str] = QUALITY_GATE_REQUIRED_TESTS) -> bool:
    normalized_nodeid = str(nodeid or "").strip().replace("\\", "/")
    node_path = normalized_nodeid.split("::", 1)[0]
    return any(
        node_path == required_path or normalized_nodeid.startswith(required_path + "::")
        for required_path in iter_required_tests(required_tests)
    )


def iter_required_regression_groups(
    groups: Optional[Sequence[RegistryGroup]] = None,
) -> List[Dict[str, Any]]:
    source = REQUIRED_REGRESSION_GROUPS if groups is None else groups
    rows: List[Dict[str, Any]] = []
    seen_group_ids = set()
    for raw_group in source:
        group_id = raw_group["group_id"]
        if not group_id:
            raise ValueError("required regression group_id is empty")
        if group_id in seen_group_ids:
            raise ValueError("required regression group_id is duplicated: " + group_id)
        seen_group_ids.add(group_id)
        target_paths = normalize_test_paths(raw_group["target_paths"])
        if not target_paths:
            raise ValueError("required regression group targets are empty: " + group_id)
        rows.append(
            {
                "group_id": group_id,
                "label": raw_group["label"],
                "target_paths": target_paths,
                "input_file_scopes": _normalize_scope_paths(raw_group["input_file_scopes"]),
                "config_file_scopes": _normalize_scope_paths(raw_group["config_file_scopes"]),
                "tool_file_scopes": _normalize_scope_paths(raw_group["tool_file_scopes"]),
                "dependency_file_scopes": _normalize_scope_paths(raw_group["dependency_file_scopes"]),
                "env_keys": _normalize_env_keys(raw_group["env_keys"]),
            }
        )
    return rows


def iter_required_regression_common_scope_policy() -> Dict[str, List[str]]:
    return {
        "input_file_scopes": _normalize_scope_paths(REQUIRED_REGRESSION_COMMON_SCOPES["input_file_scopes"]),
        "config_file_scopes": _normalize_scope_paths(REQUIRED_REGRESSION_COMMON_SCOPES["config_file_scopes"]),
        "tool_file_scopes": _normalize_scope_paths(REQUIRED_REGRESSION_COMMON_SCOPES["tool_file_scopes"]),
        "dependency_file_scopes": _normalize_scope_paths(REQUIRED_REGRESSION_COMMON_SCOPES["dependency_file_scopes"]),
        "env_keys": _normalize_env_keys(REQUIRED_REGRESSION_COMMON_SCOPES["env_keys"]),
    }


def validate_required_regression_group_coverage(
    required_paths: Sequence[str],
    groups: Optional[Sequence[RegistryGroup]] = None,
) -> Dict[str, Any]:
    required_set = set(required_paths)
    group_rows = iter_required_regression_groups(groups)
    flat_targets: List[str] = []
    target_to_groups: Dict[str, List[str]] = {}
    for group in group_rows:
        group_id = group["group_id"]
        for target in group["target_paths"]:
            flat_targets.append(target)
            target_to_groups.setdefault(target, []).append(group_id)

    duplicates = []
    for target, owning_groups in sorted(target_to_groups.items()):
        if len(owning_groups) > 1:
            duplicates.append(
                {
                    "path": target,
                    "groups": owning_groups,
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
        "required_target_paths": list(required_paths),
        "group_definitions": group_rows,
    }


def scope_matches_path(path: str, scope: str) -> bool:
    """门禁范围（规格与登记表的 `*_file_scopes`、`target_paths`）匹配仓库相对路径的唯一实现。

    `./` 加文件名通配（如 `./*.json`）只匹配仓库根下的文件，与路径角色的根目录通配同一判定
    （`tools.path_roles.matches_root_file`）。其余范围按 fnmatch 宽语义：`*` 跨 `/`，所以 `*.py`
    匹配全仓 `.py`；含 `**/` 的范围再按去掉 `**/` 匹配一次，让 `tools/**/*.py` 也覆盖 `tools/x.py`。
    """
    if scope.startswith(ROOT_FILE_SCOPE_PREFIX):
        return matches_root_file(path, scope[len(ROOT_FILE_SCOPE_PREFIX):])
    return fnmatch.fnmatch(path, scope) or ("**/" in scope and fnmatch.fnmatch(path, scope.replace("**/", "")))


def collect_production_source_files(repo_root: str) -> List[str]:
    files: List[str] = []
    for rel_root in PRODUCTION_SOURCE_ROOTS:
        abs_root = os.path.join(repo_root, rel_root.replace("/", os.sep))
        if os.path.isfile(abs_root):
            files.append(rel_root)
            continue
        if not os.path.isdir(abs_root):
            continue
        for dirpath, dirnames, filenames in os.walk(abs_root):
            dirnames[:] = [name for name in dirnames if name not in _SKIP_DIR_NAMES]
            for filename in filenames:
                if not filename.endswith(PRODUCTION_SOURCE_EXTENSIONS):
                    continue
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(abs_path, repo_root).replace("\\", "/")
                files.append(rel_path)
    return sorted(dict.fromkeys(files))


def _uncovered_production_sources(
    repo_root: str,
    group_rows: Sequence[Mapping[str, Any]],
) -> List[str]:
    scope_globs: Set[str] = set()
    for group in group_rows:
        for key in _SCOPE_KEYS:
            scope_globs.update(group[key])
    source_files = collect_production_source_files(repo_root)
    return [
        rel_path
        for rel_path in source_files
        if not any(scope_matches_path(rel_path, scope) for scope in scope_globs)
    ]


def validate_test_registry(
    repo_root: str,
    *,
    required_paths: Optional[Sequence[str]] = None,
    groups: Optional[Sequence[RegistryGroup]] = None,
) -> Dict[str, Any]:
    targets = iter_required_tests(required_paths) if required_paths is not None else iter_required_tests()
    coverage = validate_required_regression_group_coverage(targets, groups=groups)
    uncovered_sources = _uncovered_production_sources(
        repo_root,
        coverage["group_definitions"],
    )
    coverage["uncovered_sources"] = uncovered_sources
    problems: List[str] = []
    if coverage["missing"]:
        problems.append("missing=" + ", ".join(coverage["missing"]))
    if coverage["unknown"]:
        problems.append("unknown=" + ", ".join(coverage["unknown"]))
    if coverage["duplicates"]:
        problems.append("duplicates=" + ", ".join(row["path"] for row in coverage["duplicates"]))
    if uncovered_sources:
        problems.append("uncovered_sources=" + ", ".join(uncovered_sources))
    if problems:
        raise ValueError("test_registry coverage validation failed: " + "; ".join(problems))
    return coverage


__all__ = [
    "PRODUCTION_SOURCE_EXTENSIONS",
    "PRODUCTION_SOURCE_ROOTS",
    "QUALITY_GATE_REQUIRED_TESTS",
    "QUALITY_GATE_STARTUP_REGRESSION_ARGS",
    "REQUIRED_REGRESSION_COMMON_SCOPES",
    "REQUIRED_REGRESSION_GROUPS",
    "collect_production_source_files",
    "iter_required_regression_common_scope_policy",
    "iter_required_regression_groups",
    "iter_required_tests",
    "iter_startup_regressions",
    "normalize_test_paths",
    "required_test_nodeid_matches",
    "scope_matches_path",
    "validate_required_regression_group_coverage",
    "validate_test_registry",
]
