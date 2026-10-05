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
import tempfile
from fnmatch import fnmatch
from typing import Any, Dict, List, NamedTuple, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools.test_registry import (
    iter_required_regression_common_scope_policy,
    iter_required_regression_groups,
)

# Every daily run includes these two real application contracts. If an impact
# target already includes their files, that execution also supplies the smoke proof.
FOCUSED_PYTEST_NODEIDS: Tuple[str, ...] = (
    "tests/app_runtime/test_app_new_ui_create_app_smoke.py::test_app_new_ui_create_app_smoke",
    "tests/app_runtime/test_frontend_offline_static_assets.py::test_frontend_static_assets_are_offline_local",
)

_ZERO_SHA = "0" * 40


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
    pre_push_scope_known: Optional[bool] = None,
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

    if pre_push_scope_known is not None or pre_push_changed_paths or pre_push_scope_reason:
        branch_paths = ChangedPathSet(
            _dedupe_paths(list(pre_push_changed_paths)),
            True if pre_push_scope_known is None else pre_push_scope_known,
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
    pre_push_scope_known: Optional[bool] = None,
) -> DailyGateScope:
    changed = _changed_paths(
        pre_push_from_ref=pre_push_from_ref,
        pre_push_to_ref=pre_push_to_ref,
        pre_push_remote_name=pre_push_remote_name,
        pre_push_remote_ref=pre_push_remote_ref,
        pre_push_changed_paths=pre_push_changed_paths,
        pre_push_scope_reason=pre_push_scope_reason,
        pre_push_scope_known=pre_push_scope_known,
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


def _commands(
    required_targets: Sequence[str], ruff_plan: RuffPlan, *, workbench_ui_evidence: Optional[str] = None,
) -> List[Tuple[str, List[str]]]:
    if workbench_ui_evidence is not None:
        raise ValueError("--workbench-ui-evidence is retired; retained UI Node contracts run in pytest")
    commands: List[Tuple[str, List[str]]] = [
        (
            "block staged runtime artifacts",
            [sys.executable, "tools/git_hook_checks.py", "check-staged-artifacts"],
        )
    ]
    if ruff_plan.all_files:
        commands.append(("ruff check full", [sys.executable, "-m", "ruff", "check"]))
    elif ruff_plan.target_paths:
        commands.append(
            (
                "ruff check changed files",
                [sys.executable, "-m", "ruff", "check", "--force-exclude", "--", *ruff_plan.target_paths],
            )
        )

    normalized_targets = _dedupe_paths(required_targets)
    covered_files = {target for target in normalized_targets if "::" not in target}
    pytest_targets = list(normalized_targets)
    for nodeid in FOCUSED_PYTEST_NODEIDS:
        if nodeid not in pytest_targets and nodeid.split("::", 1)[0] not in covered_files:
            pytest_targets.append(nodeid)
    # One process and one collection; no xdist startup or repeated focused runs.
    commands.append(
        (
            "impact and focused pytest" if normalized_targets else "focused pytest",
            [sys.executable, "-m", "pytest", "-q", "-rfE", *pytest_targets],
        )
    )
    return commands



_FAILED_SUMMARY_RE = re.compile(r"^(FAILED|ERROR)\s+(\S+)")


def _extract_failed_nodeids(output: str) -> List[str]:
    """从 pytest 短摘要（-rfE）里抽出 FAILED/ERROR 的用例标识，供失败时直接点名。

    只认形如 `FAILED <nodeid>` / `ERROR <path.py>` 的真用例标识（含 :: 或以 .py 结尾），
    借此避开 pytest log_cli 输出的 `ERROR <logger>:...` 这类日志行被误抓成用例。
    """
    found: List[str] = []
    for raw_line in str(output or "").splitlines():
        match = _FAILED_SUMMARY_RE.match(raw_line.strip())
        if not match:
            continue
        target = match.group(2)
        if "::" not in target and not target.endswith(".py"):
            continue
        entry = f"{match.group(1)} {target}"
        if entry not in found:
            found.append(entry)
    return found


def _failure_log_path() -> Optional[str]:
    """失败日志落点：.git/aps-hook-cache 下单个固定文件，覆盖写、最多常驻一份、随 git 忽略隐身。

    任何解析/建目录异常都吞掉返回 None——失败日志只是排错便利，绝不能反过来影响门禁判定。
    """
    try:
        common_dir = _git_stdout(["rev-parse", "--git-common-dir"])
        if not common_dir:
            return None
        if not os.path.isabs(common_dir):
            common_dir = os.path.join(REPO_ROOT, common_dir)
        cache_dir = os.path.join(os.path.abspath(common_dir), "aps-hook-cache")
        os.makedirs(cache_dir, exist_ok=True)
        return os.path.join(cache_dir, "daily-gate-last-failure.log")
    except Exception:
        return None


def _persist_failure_log(log_path: Optional[str], chunks: Sequence[str]) -> Optional[str]:
    """把本次运行的全程输出写到单个失败日志（覆盖写）。返回写成功的路径，失败返回 None。"""
    if not log_path:
        return None
    try:
        with open(log_path, "w", encoding="utf-8", errors="replace") as handle:
            handle.write("".join(chunks))
    except OSError:
        return None
    return log_path


def _remove_failure_log(log_path: Optional[str]) -> None:
    """门禁通过后清掉上一轮残留的失败日志，让「文件在＝上次失败」语义干净。"""
    if not log_path:
        return
    try:
        if os.path.isfile(log_path):
            os.remove(log_path)
    except OSError:
        pass


def _run_step_streaming(command: Sequence[str], env: Dict[str, str]) -> Tuple[int, str]:
    """跑一步命令：实时把输出转发到终端，同时捕获全文返回（供失败点名 + 落盘）。"""
    if sys.platform == "win32" and list(command[1:3]) == ["-m", "pytest"] and len(subprocess.list2cmdline(command)) >= 32767:
        # pytest reads one complete argument per line, preserving markers and paths with spaces.
        with tempfile.TemporaryDirectory(prefix="aps-pytest-args-") as argument_dir:
            argument_file = os.path.join(argument_dir, "pytest.args")
            with open(argument_file, "w", encoding="utf-8") as handle:
                handle.write("\n".join(command[3:]) + "\n")
            return _run_step_streaming([*command[:3], "@" + argument_file], env)
    process = subprocess.Popen(
        list(command),
        cwd=REPO_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    captured: List[str] = []
    stream = process.stdout
    assert stream is not None
    for line in stream:
        sys.stdout.write(line)
        sys.stdout.flush()
        captured.append(line)
    stream.close()
    return int(process.wait()), "".join(captured)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fast local development gate.")
    parser.add_argument("--pre-push-from-ref", default="")
    parser.add_argument("--pre-push-to-ref", default="")
    parser.add_argument("--pre-push-remote-name", default="")
    parser.add_argument("--pre-push-remote-ref", default="")
    parser.add_argument("--pre-push-changed-path", action="append", default=[], help=argparse.SUPPRESS)
    parser.add_argument("--pre-push-scope-reason", default="", help=argparse.SUPPRESS)
    parser.add_argument("--pre-push-scope-file", default="", help=argparse.SUPPRESS)
    parser.set_defaults(pre_push_scope_known=None)
    parser.add_argument(
        "--workbench-ui-evidence", metavar="DIR", default=None,
        help="Retired option; retained UI Node contracts run in the normal pytest suite.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.pre_push_scope_file:
        try:
            with open(args.pre_push_scope_file, encoding="utf-8") as handle:
                scope = json.load(handle)
            if not isinstance(scope, dict) or type(scope.get("scope_known")) is not bool:
                raise ValueError("scope_known must be a boolean")
            paths = scope.get("changed_paths")
            if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
                raise ValueError("changed_paths must be a list of strings")
            if not isinstance(scope.get("reason"), str):
                raise ValueError("reason must be a string")
        except (OSError, ValueError) as exc:
            parser.error("cannot read --pre-push-scope-file: " + str(exc))
        args.pre_push_changed_path = paths
        args.pre_push_scope_reason = scope["reason"]
        args.pre_push_scope_known = scope["scope_known"]
    if args.workbench_ui_evidence is not None:
        parser.error("--workbench-ui-evidence is retired; retained UI Node contracts run in pytest")
    return args


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
        pre_push_scope_known=args.pre_push_scope_known,
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

    failure_log = _failure_log_path()
    run_log: List[str] = []

    def _announce_failure_log() -> None:
        saved = _persist_failure_log(failure_log, run_log)
        if saved:
            print(f"[daily-fast-gate] 完整输出已留存：{saved}", file=sys.stderr, flush=True)

    commands = _commands(impact_plan.target_paths, ruff_plan, workbench_ui_evidence=args.workbench_ui_evidence)
    for index, (label, command) in enumerate(commands, start=1):
        print(f"[daily-fast-gate] {index}/{len(commands)} {label}", flush=True)
        returncode, step_output = _run_step_streaming(command, env)
        run_log.append(f"\n# [{index}/{len(commands)}] {label}\n")
        run_log.append(step_output)
        if returncode != 0:
            print(f"[daily-fast-gate] failed: {label} returncode={returncode}", file=sys.stderr, flush=True)
            failed_nodeids = _extract_failed_nodeids(step_output)
            if failed_nodeids:
                print("[daily-fast-gate] 失败用例（照这几个直接复跑即可定位）：", file=sys.stderr, flush=True)
                for entry in failed_nodeids:
                    print(f"  - {entry}", file=sys.stderr, flush=True)
            _announce_failure_log()
            return returncode
    _remove_failure_log(failure_log)
    print("[daily-fast-gate] passed", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
