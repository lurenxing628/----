"""日常门禁的范围计划：本次改了哪些路径，据此决定 pytest 影响组、ruff 范围与要跑的扫描器。

日常门禁 CLI（`scripts/run_daily_quality_gate.py`）与 pre-push hook（`tools/git_hook_checks.py`）
都只用这里的公开机制：先取得变更路径（`ChangedPathSet`），再由 `plan_daily_gate_scope` 一次算出计划，
同一份变更路径得到同一份计划。扫描器规格取自 `tools/quality_gate_shared.py` 的共同规格。
"""

from __future__ import annotations

import os
import subprocess
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

from tools.long_gate_schema import decode_nul_paths
from tools.quality_gate_shared import (
    BOUNDARY_RATCHET_CHECK_IDS,
    IMPORT_CYCLE_CHECK_IDS,
    GateCheckSpec,
    build_quality_gate_check_specs,
)
from tools.test_registry import (
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
    scope_matches_path,
)

ZERO_SHA = "0" * 40


class ChangedPathSet(NamedTuple):
    paths: List[str]
    scope_known: bool
    reason: str


class ImpactPlan(NamedTuple):
    target_paths: List[str]
    selected_group_ids: List[str]
    all_required_groups: bool
    reason: str


class RuffPlan(NamedTuple):
    target_paths: List[str]
    all_files: bool
    reason: str
    boundary_scanners: Tuple[str, ...] = ()


class DailyGateScope(NamedTuple):
    changed: ChangedPathSet
    impact_plan: ImpactPlan
    ruff_plan: RuffPlan


_DOC_ONLY_EXTENSIONS: Tuple[str, ...] = (".md", ".rst", ".txt", ".adoc")
_CODESTABLE_CONTENT_EXTENSIONS: Tuple[str, ...] = (".md", ".yaml", ".yml", ".json", ".txt", ".rst")
_DOC_ONLY_PREFIXES: Tuple[str, ...] = ("docs/", "开发文档/", "audit/")
_DOC_ONLY_EXCLUDED_PATHS = {
    "开发文档/技术债务治理台账.md",
    "开发文档/阶段留痕与验收记录.md",
}
_RUFF_CONFIG_PATTERNS: Tuple[str, ...] = (
    "pyproject.toml",
    "ruff.toml",
    ".ruff.toml",
    "setup.cfg",
    "tox.ini",
)


def scanner_specs(repo_root: str) -> Tuple[GateCheckSpec, ...]:
    """日常门禁跑的七个扫描器：五个共用棘轮与两档循环依赖，取完整门禁的同一份规格。"""
    specs_by_id = {spec.check_id: spec for spec in build_quality_gate_check_specs(repo_root)}
    return tuple(specs_by_id[check_id] for check_id in (*BOUNDARY_RATCHET_CHECK_IDS, *IMPORT_CYCLE_CHECK_IDS))


def _spec_trigger_scopes(spec: GateCheckSpec) -> Tuple[str, ...]:
    """扫描器规格声明的全部范围：读取的输入、基线、工具、依赖与只看存在性的输入。"""
    return (
        *spec.input_file_scopes,
        *spec.config_file_scopes,
        *spec.tool_file_scopes,
        *spec.dependency_file_scopes,
        *spec.existence_file_scopes,
    )


def _dedupe_paths(paths: Sequence[str]) -> List[str]:
    return list(dict.fromkeys(path for path in paths if path))


def _git_name_only(repo_root: str, args: Sequence[str]) -> Optional[List[str]]:
    result = subprocess.run(["git", *args], cwd=repo_root, capture_output=True)
    if result.returncode != 0:
        return None
    return _dedupe_paths(decode_nul_paths(result.stdout))


def _git_stdout(repo_root: str, args: Sequence[str]) -> Optional[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _git_ref_exists(repo_root: str, ref: str) -> bool:
    value = ref.strip()
    if not value or value == ZERO_SHA:
        return False
    result = subprocess.run(
        ["git", "cat-file", "-e", value + "^{commit}"],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _git_lines(repo_root: str, args: Sequence[str]) -> Optional[List[str]]:
    output = _git_stdout(repo_root, args)
    if output is None:
        return None
    return [line.strip() for line in output.splitlines() if line.strip()]


def branch_diff_paths(repo_root: str) -> ChangedPathSet:
    """当前分支相对上游的已提交变更。"""
    upstream = _git_stdout(repo_root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if not upstream:
        return ChangedPathSet([], False, "upstream not found")

    merge_base = _git_stdout(repo_root, ["merge-base", "HEAD", upstream])
    if not merge_base:
        return ChangedPathSet([], False, "merge-base not found")

    paths = _git_name_only(repo_root, ["diff", "--name-only", "-z", merge_base + "..HEAD"])
    if paths is None:
        return ChangedPathSet([], False, "branch diff failed")
    return ChangedPathSet(paths, True, "")


def _new_branch_pre_push_paths(repo_root: str, to_ref: str, remote_name: str) -> ChangedPathSet:
    if not _git_ref_exists(repo_root, to_ref):
        return ChangedPathSet([], False, "pre-push to-ref not found")
    if not remote_name.strip():
        return ChangedPathSet([], False, "pre-push remote name not found")

    ancestors = _git_lines(
        repo_root, ["rev-list", to_ref, "--topo-order", "--reverse", "--not", "--remotes=" + remote_name]
    )
    if ancestors is None:
        return ChangedPathSet([], False, "pre-push new branch ancestry detection failed")
    if not ancestors:
        return ChangedPathSet([], True, "pre-push has no new commits against remote")

    first_ancestor = ancestors[0]
    roots = _git_lines(repo_root, ["rev-list", "--max-parents=0", to_ref])
    if roots is None:
        return ChangedPathSet([], False, "pre-push root commit detection failed")
    if first_ancestor in set(roots):
        paths = _git_name_only(repo_root, ["ls-tree", "-r", "--name-only", "-z", to_ref])
        if paths is None:
            return ChangedPathSet([], False, "pre-push root tree listing failed")
        return ChangedPathSet(paths, True, "pre-push new branch includes root commit")

    source = _git_stdout(repo_root, ["rev-parse", first_ancestor + "^"])
    if not source:
        return ChangedPathSet([], False, "pre-push new branch source detection failed")
    paths = _git_name_only(repo_root, ["diff", "--name-only", "-z", source + ".." + to_ref])
    if paths is None:
        return ChangedPathSet([], False, "pre-push new branch diff failed")
    return ChangedPathSet(paths, True, "pre-push new branch diff")


def pre_push_diff_paths(repo_root: str, from_ref: str, to_ref: str, remote_name: str) -> ChangedPathSet:
    """推送目标 from_ref..to_ref 的已提交变更；没给 to_ref 时取当前分支相对上游的变更。"""
    to_value = to_ref.strip()
    from_value = from_ref.strip()
    if not to_value:
        return branch_diff_paths(repo_root)
    if to_value == ZERO_SHA:
        return ChangedPathSet([], True, "pre-push delete ref")
    if not _git_ref_exists(repo_root, to_value):
        return ChangedPathSet([], False, "pre-push to-ref not found")
    if _git_ref_exists(repo_root, from_value):
        paths = _git_name_only(repo_root, ["diff", "--name-only", "-z", from_value + ".." + to_value])
        if paths is None:
            return ChangedPathSet([], False, "pre-push ref diff failed")
        return ChangedPathSet(paths, True, "pre-push ref diff")
    return _new_branch_pre_push_paths(repo_root, to_value, remote_name)


def with_local_changes(repo_root: str, target: ChangedPathSet) -> ChangedPathSet:
    """本地未提交的变更（未暂存、已暂存、未跟踪）并上目标变更；范围是否已知与理由取目标的。"""
    changed: List[str] = []
    for args in (
        ["diff", "--name-only", "-z"],
        ["diff", "--cached", "--name-only", "-z"],
        ["ls-files", "--others", "--exclude-standard", "-z"],
    ):
        paths = _git_name_only(repo_root, args)
        if paths is None:
            return ChangedPathSet([], False, "git changed path detection failed")
        changed.extend(paths)
    return ChangedPathSet(_dedupe_paths([*changed, *target.paths]), target.scope_known, target.reason)


def _common_scope_patterns(common_policy: Dict[str, List[str]]) -> List[str]:
    patterns: List[str] = []
    for key in (
        "input_file_scopes",
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        patterns.extend(common_policy[key])
    return patterns


def _common_static_scope_patterns(common_policy: Dict[str, List[str]]) -> List[str]:
    patterns: List[str] = list(_RUFF_CONFIG_PATTERNS)
    for key in (
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        patterns.extend(common_policy[key])
    return patterns


def _group_scope_patterns(group: Dict[str, Any]) -> List[str]:
    patterns: List[str] = []
    for key in (
        "target_paths",
        "input_file_scopes",
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        patterns.extend(group[key])
    return patterns


def _matches_any(path: str, scopes: Sequence[str]) -> bool:
    return any(scope_matches_path(path, scope) for scope in scopes)


def _is_readme_path(path: str) -> bool:
    return path.rsplit("/", 1)[-1].lower() == "readme.md"


def _is_docs_only_path(path: str) -> bool:
    lowered = path.lower()
    if path in _DOC_ONLY_EXCLUDED_PATHS:
        return False
    if _is_readme_path(path):
        return True
    if path.startswith(".codestable/") and not path.startswith(".codestable/tools/"):
        return lowered.endswith(_CODESTABLE_CONTENT_EXTENSIONS)
    if path.startswith(_DOC_ONLY_PREFIXES):
        return lowered.endswith(_DOC_ONLY_EXTENSIONS)
    return False


def _build_impact_plan(changed: ChangedPathSet) -> ImpactPlan:
    groups = iter_required_regression_groups()
    common_policy = iter_required_regression_common_scope_policy()
    all_targets = _dedupe_paths([target for group in groups for target in group["target_paths"]])
    all_group_ids = [group["group_id"] for group in groups]

    if not changed.scope_known:
        return ImpactPlan(all_targets, all_group_ids, True, changed.reason)

    if not changed.paths:
        return ImpactPlan([], [], False, "no changed paths detected")

    if all(_is_docs_only_path(path) for path in changed.paths):
        return ImpactPlan([], [], False, "documentation-only changed paths")

    selected_group_ids: List[str] = []
    selected_targets: List[str] = []
    common_patterns = _common_scope_patterns(common_policy)
    group_scopes = [(group["group_id"], _group_scope_patterns(group), group["target_paths"]) for group in groups]
    for path in changed.paths:
        if _is_docs_only_path(path):
            continue
        if _matches_any(path, common_patterns):
            return ImpactPlan(all_targets, all_group_ids, True, "common quality gate scope changed: " + path)

        matched_group = False
        for group_id, scope_patterns, group_targets in group_scopes:
            if not _matches_any(path, scope_patterns):
                continue
            matched_group = True
            if group_id not in selected_group_ids:
                selected_group_ids.append(group_id)
            selected_targets.extend(group_targets)

        if not matched_group:
            return ImpactPlan(
                all_targets,
                all_group_ids,
                True,
                "changed path is outside known required regression scopes: " + path,
            )

    return ImpactPlan(_dedupe_paths(selected_targets), selected_group_ids, False, "matched changed paths")


def _build_ruff_plan(
    repo_root: str, changed: ChangedPathSet, impact_plan: ImpactPlan, specs: Sequence[GateCheckSpec]
) -> RuffPlan:
    all_scanner_ids = tuple(spec.check_id for spec in specs)
    if not changed.scope_known:
        return RuffPlan([], True, changed.reason, all_scanner_ids)

    if impact_plan.all_required_groups:
        return RuffPlan([], True, impact_plan.reason, all_scanner_ids)

    static_patterns = _common_static_scope_patterns(iter_required_regression_common_scope_policy())
    for path in changed.paths:
        if _matches_any(path, static_patterns):
            return RuffPlan([], True, "common static quality scope changed: " + path, all_scanner_ids)

    # 删除 Python 文件同样会改变扫描结果（唯一调用方被删、模块被删后留下失效路径），所以扫描器看全部 Python 变更；
    # ruff 只检查还存在的文件。
    python_paths = [path for path in changed.paths if path.endswith(".py")]
    if python_paths:
        target_paths = [path for path in python_paths if os.path.isfile(os.path.join(repo_root, path))]
        if target_paths:
            return RuffPlan(target_paths, False, "changed Python files", all_scanner_ids)
        return RuffPlan([], False, "changed Python files are all deleted: scanners only, ruff skipped", all_scanner_ids)
    # 没有 Python 变更时，改动路径落在哪个扫描器规格声明的范围里就跑哪个。
    scanners: List[str] = []
    scope_paths: List[str] = []
    for spec in specs:
        scopes = _spec_trigger_scopes(spec)
        matched = [path for path in changed.paths if _matches_any(path, scopes)]
        if matched:
            scanners.append(spec.check_id)
            scope_paths.extend(matched)
    if scanners:
        return RuffPlan([], False, "scanner scopes changed: " + ", ".join(_dedupe_paths(scope_paths)), tuple(scanners))
    return RuffPlan([], False, "no changed Python files")


def plan_daily_gate_scope(repo_root: str, changed: ChangedPathSet, specs: Sequence[GateCheckSpec]) -> DailyGateScope:
    """同一份变更路径得到的唯一计划：pytest 影响组，以及 ruff 与扫描器（specs 取自 `scanner_specs`）。"""
    impact_plan = _build_impact_plan(changed)
    return DailyGateScope(changed, impact_plan, _build_ruff_plan(repo_root, changed, impact_plan, specs))


def daily_gate_scope_payload(scope: DailyGateScope) -> Dict[str, Any]:
    """计划的 JSON 形状：hook 写给目标 worktree 的范围文件与日常缓存键都用它。"""
    changed, impact_plan, ruff_plan = scope
    return {
        "scope_known": changed.scope_known,
        "reason": changed.reason,
        "changed_paths": changed.paths,
        "impact_pytest": {
            "target_paths": impact_plan.target_paths,
            "selected_group_ids": impact_plan.selected_group_ids,
            "all_required_groups": impact_plan.all_required_groups,
            "reason": impact_plan.reason,
        },
        "ruff": {
            "target_paths": ruff_plan.target_paths,
            "all_files": ruff_plan.all_files,
            "reason": ruff_plan.reason,
            "boundary_scanners": list(ruff_plan.boundary_scanners),
        },
    }


__all__ = [
    "ZERO_SHA",
    "ChangedPathSet",
    "DailyGateScope",
    "ImpactPlan",
    "RuffPlan",
    "branch_diff_paths",
    "daily_gate_scope_payload",
    "plan_daily_gate_scope",
    "pre_push_diff_paths",
    "scanner_specs",
    "with_local_changes",
]
