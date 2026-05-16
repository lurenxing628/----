#!/usr/bin/env python3
"""Run the fast local development gate.

This script is intentionally smaller than scripts/run_quality_gate.py. It is a
push-time smoke gate for obvious mistakes, not the final clean proof.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from fnmatch import fnmatch
from typing import Dict, List, NamedTuple, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.test_registry import (
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
)

FOCUSED_PYTEST_NODEIDS: Tuple[str, ...] = (
    "tests/test_long_gate_full_test_debt_cache.py::test_validated_previous_success_accepts_zero_returncode",
    "tests/test_long_gate_full_test_debt_cache.py::test_nodeid_incremental_plan_selects_changed_test_file_nodeids",
    "tests/test_long_gate_required_regression_cache.py::test_required_entry_comes_from_real_command_plan_and_enables_only_current_cache_entries",
    "tests/test_long_gate_startup_regression_cache.py::test_startup_entry_comes_from_real_command_plan_and_enables_only_current_cache_entries",
    "tests/test_scheduler_batches_page_viewmodel.py::test_batches_filter_state_preserves_default_and_empty_status_contract",
    "tests/test_scheduler_batches_page_viewmodel.py::test_batch_rows_filter_ready_and_add_public_labels",
    "tests/test_ui_geometry_html_contract.py::test_ui_smoke_pages_render_expected_html_contract",
    "tests/test_architecture_fitness.py::test_viewmodels_do_not_import_flask_or_services_or_repositories_or_routes",
)

_COLLECT_COUNT_RE = re.compile(r"\b(\d+)\s+(?:tests?|items?) collected\b")
_TAIL_LINES = 40


class ChangedPathSet(NamedTuple):
    paths: List[str]
    scope_known: bool
    reason: str


class ImpactPlan(NamedTuple):
    target_paths: List[str]
    selected_group_ids: List[str]
    all_required_groups: bool
    reason: str


def _gate_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _normalize_path(path: str) -> str:
    return str(path or "").strip().replace("\\", "/").lstrip("./")


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


def _changed_paths() -> ChangedPathSet:
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


def _build_impact_plan(changed: ChangedPathSet) -> ImpactPlan:
    groups = iter_required_regression_groups()
    common_policy = iter_required_regression_common_scope_policy()
    all_targets = _all_group_targets(groups)

    if not changed.scope_known:
        return ImpactPlan(all_targets, [str(group["group_id"]) for group in groups], True, changed.reason)

    if not changed.paths:
        return ImpactPlan([], [], False, "no changed paths detected")

    selected_group_ids: List[str] = []
    selected_targets: List[str] = []
    common_patterns = _common_scope_patterns(common_policy)
    for path in changed.paths:
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


def _commands(required_targets: Sequence[str]) -> List[Tuple[str, List[str]]]:
    commands = [
        (
            "block staged runtime artifacts",
            [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"],
        ),
        (
            "ruff check",
            [sys.executable, "-m", "ruff", "check"],
        ),
    ]
    normalized_targets = _dedupe_paths(required_targets)
    if normalized_targets:
        commands.append(
            (
                "impact pytest",
                [sys.executable, "-m", "pytest", "-q", *normalized_targets],
            )
        )
    commands.append(
        (
            "focused pytest",
            [sys.executable, "-m", "pytest", "-q", *FOCUSED_PYTEST_NODEIDS],
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


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv:
        print("run_daily_quality_gate.py does not accept arguments", file=sys.stderr)
        return 2

    print("FAST DAILY GATE ONLY: not final clean proof", flush=True)
    print("快速日常门禁只挡明显问题，不声明 full-test-debt / clean proof。", flush=True)
    print(
        "最终收口必须运行：PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8 "
        ".venv/bin/python scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
        flush=True,
    )
    env = _gate_env()
    changed = _changed_paths()
    impact_plan = _build_impact_plan(changed)
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

    collect_returncode = _run_collect_only(env)
    if collect_returncode != 0:
        return collect_returncode

    commands = _commands(impact_plan.target_paths)
    for index, (label, command) in enumerate(commands, start=1):
        print(f"[daily-fast-gate] {index}/{len(commands)} {label}", flush=True)
        returncode = subprocess.call(command, cwd=REPO_ROOT, env=env)
        if int(returncode) != 0:
            print(f"[daily-fast-gate] failed: {label} returncode={returncode}", file=sys.stderr, flush=True)
            return int(returncode)
    print("[daily-fast-gate] passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
