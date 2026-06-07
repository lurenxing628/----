#!/usr/bin/env python3
"""Run the fast local development gate.

This script is intentionally smaller than scripts/run_quality_gate.py. It is a
push-time smoke gate for obvious mistakes, not the final clean proof.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.test_registry import (
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
)

# 每次 push 无条件跑的冒烟用例。只保留真业务冒烟（批次页 viewmodel + UI 页面 HTML 契约）。
# P0.1（test-gate-cleanup）：移除 4 个 test_long_gate_*_cache 与 test_architecture_fitness 等
# 门禁自指用例——它们已在各自 required regression group 的 target_paths 与 CI 全量门禁里覆盖，
# 无需在每次 push 的 focused 冒烟里重复支付（这几个又慢，是最慢榜常客）。
FOCUSED_PYTEST_NODEIDS: Tuple[str, ...] = (
    "tests/schedule/route_view/test_scheduler_batches_page_viewmodel.py::test_batches_filter_state_preserves_default_and_empty_status_contract",
    "tests/schedule/route_view/test_scheduler_batches_page_viewmodel.py::test_batch_rows_filter_ready_and_add_public_labels",
    "tests/app_runtime/test_ui_geometry_html_contract.py::test_ui_smoke_pages_render_expected_html_contract",
)

_COLLECT_COUNT_RE = re.compile(r"\b(\d+)\s+(?:tests?|items?) collected\b")
_TAIL_LINES = 40
_ZERO_SHA = "0" * 40
# pytest 在"未收集到任何用例"时的退出码（ExitCode.NO_TESTS_COLLECTED）。impact 集按 serial/not-serial
# 分两步跑时，某一类本次为空＝合法空集，仅对这两步容忍此退出码（focused 等其余步骤照常按失败处理）。
_PYTEST_NO_TESTS_EXITCODE = 5


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


def _gate_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _normalize_path(path: str) -> str:
    normalized = str(path or "").strip().replace("\\", "/")
    while normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _dedupe_paths(paths: Sequence[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for raw_path in paths:
        path = _normalize_path(raw_path)
        if not path or path in seen:
            continue
        seen.add(path)
        out.append(path)
    return out


def _git_name_only(args: Sequence[str]) -> Optional[List[str]]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return _dedupe_paths(result.stdout.splitlines())


def _git_stdout(args: Sequence[str]) -> Optional[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _stable_hash(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _git_success(args: Sequence[str]) -> bool:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def _git_ref_exists(ref: str) -> bool:
    value = str(ref or "").strip()
    if not value or value == _ZERO_SHA:
        return False
    return _git_success(["cat-file", "-e", value + "^{commit}"])


def _git_lines(args: Sequence[str]) -> Optional[List[str]]:
    output = _git_stdout(args)
    if output is None:
        return None
    return [line.strip() for line in output.splitlines() if line.strip()]


def _branch_diff_paths() -> ChangedPathSet:
    upstream = _git_stdout(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"])
    if not upstream:
        return ChangedPathSet([], False, "upstream not found")

    merge_base = _git_stdout(["merge-base", "HEAD", upstream])
    if not merge_base:
        return ChangedPathSet([], False, "merge-base not found")

    paths = _git_name_only(["diff", "--name-only", merge_base + "..HEAD"])
    if paths is None:
        return ChangedPathSet([], False, "branch diff failed")
    return ChangedPathSet(paths, True, "")


def _new_branch_pre_push_paths(to_ref: str, remote_name: str) -> ChangedPathSet:
    if not _git_ref_exists(to_ref):
        return ChangedPathSet([], False, "pre-push to-ref not found")
    if not str(remote_name or "").strip():
        return ChangedPathSet([], False, "pre-push remote name not found")

    ancestors = _git_lines(["rev-list", to_ref, "--topo-order", "--reverse", "--not", "--remotes=" + remote_name])
    if ancestors is None:
        return ChangedPathSet([], False, "pre-push new branch ancestry detection failed")
    if not ancestors:
        return ChangedPathSet([], True, "pre-push has no new commits against remote")

    first_ancestor = ancestors[0]
    roots = _git_lines(["rev-list", "--max-parents=0", to_ref])
    if roots is None:
        return ChangedPathSet([], False, "pre-push root commit detection failed")
    if first_ancestor in set(roots):
        paths = _git_name_only(["ls-tree", "-r", "--name-only", to_ref])
        if paths is None:
            return ChangedPathSet([], False, "pre-push root tree listing failed")
        return ChangedPathSet(paths, True, "pre-push new branch includes root commit")

    source = _git_stdout(["rev-parse", first_ancestor + "^"])
    if not source:
        return ChangedPathSet([], False, "pre-push new branch source detection failed")
    paths = _git_name_only(["diff", "--name-only", source + ".." + to_ref])
    if paths is None:
        return ChangedPathSet([], False, "pre-push new branch diff failed")
    return ChangedPathSet(paths, True, "pre-push new branch diff")


def _pre_push_diff_paths(from_ref: str, to_ref: str, remote_name: str, remote_ref: str = "") -> ChangedPathSet:
    del remote_ref
    to_value = str(to_ref or "").strip()
    from_value = str(from_ref or "").strip()
    if not to_value:
        return _branch_diff_paths()
    if to_value == _ZERO_SHA:
        return ChangedPathSet([], True, "pre-push delete ref")
    if not _git_ref_exists(to_value):
        return ChangedPathSet([], False, "pre-push to-ref not found")
    if _git_ref_exists(from_value):
        paths = _git_name_only(["diff", "--name-only", from_value + ".." + to_value])
        if paths is None:
            return ChangedPathSet([], False, "pre-push ref diff failed")
        return ChangedPathSet(paths, True, "pre-push ref diff")
    return _new_branch_pre_push_paths(to_value, remote_name)


def _changed_paths(
    *,
    pre_push_from_ref: str = "",
    pre_push_to_ref: str = "",
    pre_push_remote_name: str = "",
    pre_push_remote_ref: str = "",
    pre_push_changed_paths: Sequence[str] = (),
    pre_push_scope_reason: str = "",
) -> ChangedPathSet:
    local_sources = (
        ["diff", "--name-only"],
        ["diff", "--cached", "--name-only"],
        ["ls-files", "--others", "--exclude-standard"],
    )
    changed: List[str] = []
    for args in local_sources:
        paths = _git_name_only(args)
        if paths is None:
            return ChangedPathSet([], False, "git changed path detection failed")
        changed.extend(paths)

    if pre_push_changed_paths:
        branch_paths = ChangedPathSet(
            _dedupe_paths(list(pre_push_changed_paths)),
            True,
            str(pre_push_scope_reason or "pre-push supplied changed paths"),
        )
    elif pre_push_from_ref or pre_push_to_ref:
        branch_paths = _pre_push_diff_paths(
            pre_push_from_ref,
            pre_push_to_ref,
            pre_push_remote_name,
            remote_ref=pre_push_remote_ref,
        )
    else:
        branch_paths = _branch_diff_paths()
    changed.extend(branch_paths.paths)
    return ChangedPathSet(_dedupe_paths(changed), branch_paths.scope_known, branch_paths.reason)


def _path_matches_pattern(path: str, pattern: str) -> bool:
    normalized_path = _normalize_path(path)
    normalized_pattern = _normalize_path(pattern)
    if not normalized_pattern:
        return False
    if normalized_pattern.endswith("/"):
        return normalized_path.startswith(normalized_pattern)
    if fnmatch(normalized_path, normalized_pattern):
        return True
    if "**/" in normalized_pattern:
        return fnmatch(normalized_path, normalized_pattern.replace("**/", ""))
    return False


def _path_matches_any(path: str, patterns: Sequence[str]) -> bool:
    return any(_path_matches_pattern(path, pattern) for pattern in patterns)


def _common_scope_patterns(common_policy: Dict[str, List[str]]) -> List[str]:
    patterns: List[str] = []
    for key in (
        "input_file_scopes",
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        patterns.extend(common_policy.get(key) or [])
    return patterns


def _common_static_scope_patterns(common_policy: Dict[str, List[str]]) -> List[str]:
    patterns: List[str] = list(_RUFF_CONFIG_PATTERNS)
    for key in (
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        patterns.extend(common_policy.get(key) or [])
    return patterns


def _group_scope_patterns(group: Dict[str, object]) -> List[str]:
    patterns: List[str] = []
    for key in (
        "target_paths",
        "input_file_scopes",
        "config_file_scopes",
        "tool_file_scopes",
        "dependency_file_scopes",
    ):
        values = group.get(key)
        if isinstance(values, list):
            patterns.extend(str(item) for item in values)
    return patterns


def _all_group_targets(groups: Sequence[Dict[str, object]]) -> List[str]:
    targets: List[str] = []
    for group in groups:
        raw_targets = group.get("target_paths")
        if isinstance(raw_targets, list):
            targets.extend(str(target) for target in raw_targets)
    return _dedupe_paths(targets)


def _is_readme_path(path: str) -> bool:
    return _normalize_path(path).rsplit("/", 1)[-1].lower() == "readme.md"


def _is_docs_only_path(path: str) -> bool:
    normalized = _normalize_path(path)
    lowered = normalized.lower()
    if normalized in _DOC_ONLY_EXCLUDED_PATHS:
        return False
    if _is_readme_path(normalized):
        return True
    if normalized.startswith(".codestable/") and not normalized.startswith(".codestable/tools/"):
        return lowered.endswith(_CODESTABLE_CONTENT_EXTENSIONS)
    if normalized.startswith(_DOC_ONLY_PREFIXES):
        return lowered.endswith(_DOC_ONLY_EXTENSIONS)
    return False


def _is_docs_only_change(changed: ChangedPathSet) -> bool:
    return changed.scope_known and bool(changed.paths) and all(_is_docs_only_path(path) for path in changed.paths)


def _build_impact_plan(changed: ChangedPathSet) -> ImpactPlan:
    groups = iter_required_regression_groups()
    common_policy = iter_required_regression_common_scope_policy()
    all_targets = _all_group_targets(groups)

    if not changed.scope_known:
        return ImpactPlan(all_targets, [str(group["group_id"]) for group in groups], True, changed.reason)

    if not changed.paths:
        return ImpactPlan([], [], False, "no changed paths detected")

    if _is_docs_only_change(changed):
        return ImpactPlan([], [], False, "documentation-only changed paths")

    selected_group_ids: List[str] = []
    selected_targets: List[str] = []
    common_patterns = _common_scope_patterns(common_policy)
    for path in changed.paths:
        if _is_docs_only_path(path):
            continue
        if _path_matches_any(path, common_patterns):
            return ImpactPlan(
                all_targets,
                [str(group["group_id"]) for group in groups],
                True,
                "common quality gate scope changed: " + path,
            )

        matched_group = False
        for group in groups:
            if not _path_matches_any(path, _group_scope_patterns(group)):
                continue
            matched_group = True
            group_id = str(group["group_id"])
            if group_id not in selected_group_ids:
                selected_group_ids.append(group_id)
            raw_targets = group.get("target_paths")
            if isinstance(raw_targets, list):
                selected_targets.extend(str(target) for target in raw_targets)

        if not matched_group:
            return ImpactPlan(
                all_targets,
                [str(group["group_id"]) for group in groups],
                True,
                "changed path is outside known required regression scopes: " + path,
            )

    return ImpactPlan(_dedupe_paths(selected_targets), selected_group_ids, False, "matched changed paths")


def _existing_python_paths(paths: Sequence[str]) -> List[str]:
    existing_paths: List[str] = []
    for path in _dedupe_paths(paths):
        if not path.endswith(".py"):
            continue
        absolute_path = os.path.join(REPO_ROOT, path)
        if os.path.isfile(absolute_path):
            existing_paths.append(path)
    return existing_paths


def _build_ruff_plan(changed: ChangedPathSet, impact_plan: ImpactPlan) -> RuffPlan:
    common_policy = iter_required_regression_common_scope_policy()

    if not changed.scope_known:
        return RuffPlan([], True, changed.reason)

    if impact_plan.all_required_groups:
        return RuffPlan([], True, impact_plan.reason)

    for path in changed.paths:
        if _path_matches_any(path, _common_static_scope_patterns(common_policy)):
            return RuffPlan([], True, "common static quality scope changed: " + path)

    target_paths = _existing_python_paths(changed.paths)
    if target_paths:
        return RuffPlan(target_paths, False, "changed Python files")
    return RuffPlan([], False, "no changed Python files")


def build_daily_gate_scope(
    *,
    pre_push_from_ref: str = "",
    pre_push_to_ref: str = "",
    pre_push_remote_name: str = "",
    pre_push_remote_ref: str = "",
    pre_push_changed_paths: Sequence[str] = (),
    pre_push_scope_reason: str = "",
) -> DailyGateScope:
    changed = _changed_paths(
        pre_push_from_ref=pre_push_from_ref,
        pre_push_to_ref=pre_push_to_ref,
        pre_push_remote_name=pre_push_remote_name,
        pre_push_remote_ref=pre_push_remote_ref,
        pre_push_changed_paths=pre_push_changed_paths,
        pre_push_scope_reason=pre_push_scope_reason,
    )
    impact_plan = _build_impact_plan(changed)
    ruff_plan = _build_ruff_plan(changed, impact_plan)
    return DailyGateScope(changed, impact_plan, ruff_plan)


def daily_gate_scope_payload(scope: DailyGateScope) -> Dict[str, object]:
    changed = scope.changed
    impact_plan = scope.impact_plan
    ruff_plan = scope.ruff_plan
    changed_paths = _dedupe_paths(changed.paths)
    impact_targets = _dedupe_paths(impact_plan.target_paths)
    ruff_targets = _dedupe_paths(ruff_plan.target_paths)
    payload: Dict[str, object] = {
        "scope_known": bool(changed.scope_known),
        "reason": str(changed.reason or ""),
        "changed_paths": changed_paths,
        "changed_paths_hash": _stable_hash(changed_paths),
        "impact_pytest": {
            "target_paths": impact_targets,
            "target_hash": _stable_hash(impact_targets),
            "selected_group_ids": list(impact_plan.selected_group_ids),
            "all_required_groups": bool(impact_plan.all_required_groups),
            "reason": str(impact_plan.reason or ""),
        },
        "ruff": {
            "target_paths": ruff_targets,
            "target_hash": _stable_hash(ruff_targets),
            "all_files": bool(ruff_plan.all_files),
            "reason": str(ruff_plan.reason or ""),
        },
    }
    return payload


def _commands(required_targets: Sequence[str], ruff_plan: RuffPlan) -> List[Tuple[str, List[str], bool]]:
    # 三元组 (label, command, allow_no_tests)：allow_no_tests=True 的步骤对 pytest「未收集到用例」
    # 退出码（_PYTEST_NO_TESTS_EXITCODE）视为通过（合法空集），其余步骤一律按非零失败处理。
    commands: List[Tuple[str, List[str], bool]] = [
        (
            "block staged runtime artifacts",
            [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"],
            False,
        )
    ]
    if ruff_plan.all_files:
        commands.append(("ruff check full", [sys.executable, "-m", "ruff", "check"], False))
    elif ruff_plan.target_paths:
        commands.append(
            (
                "ruff check changed files",
                [sys.executable, "-m", "ruff", "check", "--force-exclude", "--", *ruff_plan.target_paths],
                False,
            )
        )

    normalized_targets = _dedupe_paths(required_targets)
    if normalized_targets:
        # impact 集分流：not-serial 用例走 xdist 并行（-n auto --dist worksteal），serial 用例
        # （startup/runtime/portfile/long_gate 等独占进程态，口径见 tools.full_test_debt_shards）单独串行。
        # serial/perf marker 由 conftest 按 classify_nodeid / is_perf_nodeid 自动打标，这里仅按 marker
        # 表达式分流。P5.3：两步均叠加 not perf，把性能/重 E2E（PERF_FILE_PATTERNS）剔出 push 快速路径
        # （full gate 不 deselect、仍全量覆盖）。两步各自在本次 impact 集无对应类用例时会 no-tests
        # collected，故 allow_no_tests=True。
        commands.append(
            (
                "impact pytest (parallel)",
                [
                    sys.executable, "-m", "pytest", "-q",
                    "-n", "auto", "--dist", "worksteal",
                    "-m", "not serial and not perf",
                    *normalized_targets,
                ],
                True,
            )
        )
        commands.append(
            (
                "impact pytest (serial)",
                [sys.executable, "-m", "pytest", "-q", "-m", "serial and not perf", *normalized_targets],
                True,
            )
        )
    commands.append(
        (
            "focused pytest",
            [sys.executable, "-m", "pytest", "-q", *FOCUSED_PYTEST_NODEIDS],
            False,
        )
    )
    return commands


def _parse_collect_count(output: str) -> Optional[int]:
    matches = _COLLECT_COUNT_RE.findall(output)
    if matches:
        return int(matches[-1])
    if "no tests collected" in output:
        return 0
    return None


def _tail(text: str, *, line_count: int = _TAIL_LINES) -> str:
    lines = str(text or "").splitlines()
    if not lines:
        return "<empty>"
    return "\n".join(lines[-line_count:])


def _run_collect_only(env: Dict[str, str]) -> int:
    command = [sys.executable, "-m", "pytest", "--collect-only", "tests", "-q"]
    result = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
    if result.returncode == 0:
        count = _parse_collect_count(combined_output)
        if count is None:
            print(
                "[daily-fast-gate] failed: pytest collect-only did not report collected count",
                file=sys.stderr,
                flush=True,
            )
            print("[daily-fast-gate] pytest collect-only stdout tail:", file=sys.stderr, flush=True)
            print(_tail(result.stdout), file=sys.stderr, flush=True)
            print("[daily-fast-gate] pytest collect-only stderr tail:", file=sys.stderr, flush=True)
            print(_tail(result.stderr), file=sys.stderr, flush=True)
            return 1
        print(f"[daily-fast-gate] pytest collect-only collected_count={count}", flush=True)
        return 0

    print(
        f"[daily-fast-gate] failed: pytest collect-only returncode={result.returncode}",
        file=sys.stderr,
        flush=True,
    )
    print("[daily-fast-gate] pytest collect-only stdout tail:", file=sys.stderr, flush=True)
    print(_tail(result.stdout), file=sys.stderr, flush=True)
    print("[daily-fast-gate] pytest collect-only stderr tail:", file=sys.stderr, flush=True)
    print(_tail(result.stderr), file=sys.stderr, flush=True)
    return int(result.returncode)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fast local development gate.")
    parser.add_argument("--pre-push-from-ref", default="")
    parser.add_argument("--pre-push-to-ref", default="")
    parser.add_argument("--pre-push-remote-name", default="")
    parser.add_argument("--pre-push-remote-ref", default="")
    parser.add_argument("--pre-push-changed-path", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--pre-push-scope-reason", default="", help=argparse.SUPPRESS)
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)

    print("FAST DAILY GATE ONLY: not final clean proof", flush=True)
    print("快速日常门禁只挡明显问题，不声明 full-test-debt / clean proof。", flush=True)
    print(
        "最终收口必须运行：PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "
        ".venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
        flush=True,
    )
    env = _gate_env()
    scope = build_daily_gate_scope(
        pre_push_from_ref=str(args.pre_push_from_ref or ""),
        pre_push_to_ref=str(args.pre_push_to_ref or ""),
        pre_push_remote_name=str(args.pre_push_remote_name or ""),
        pre_push_remote_ref=str(args.pre_push_remote_ref or ""),
        pre_push_changed_paths=list(args.pre_push_changed_path or []),
        pre_push_scope_reason=str(args.pre_push_scope_reason or ""),
    )
    impact_plan = scope.impact_plan
    ruff_plan = scope.ruff_plan
    if impact_plan.target_paths:
        mode = "all required groups" if impact_plan.all_required_groups else "matched required groups"
        print(
            f"[daily-fast-gate] impact pytest: {mode}; "
            f"groups={','.join(impact_plan.selected_group_ids)}; "
            f"targets={len(impact_plan.target_paths)}; reason={impact_plan.reason}",
            flush=True,
        )
    else:
        print("[daily-fast-gate] impact pytest: skipped; reason=" + impact_plan.reason, flush=True)
    if ruff_plan.all_files:
        print("[daily-fast-gate] ruff: full; reason=" + ruff_plan.reason, flush=True)
    elif ruff_plan.target_paths:
        print(
            f"[daily-fast-gate] ruff: changed files; targets={len(ruff_plan.target_paths)}; "
            f"reason={ruff_plan.reason}",
            flush=True,
        )
    else:
        print("[daily-fast-gate] ruff: skipped; reason=" + ruff_plan.reason, flush=True)

    collect_returncode = _run_collect_only(env)
    if collect_returncode != 0:
        return collect_returncode

    commands = _commands(impact_plan.target_paths, ruff_plan)
    for index, (label, command, allow_no_tests) in enumerate(commands, start=1):
        print(f"[daily-fast-gate] {index}/{len(commands)} {label}", flush=True)
        returncode = int(subprocess.call(command, cwd=REPO_ROOT, env=env))
        if returncode == _PYTEST_NO_TESTS_EXITCODE and allow_no_tests:
            print(
                f"[daily-fast-gate] {label}: 本次 impact 集无该类用例"
                "（pytest no tests collected，exit 5），跳过",
                flush=True,
            )
            continue
        if returncode != 0:
            print(f"[daily-fast-gate] failed: {label} returncode={returncode}", file=sys.stderr, flush=True)
            return returncode
    print("[daily-fast-gate] passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
