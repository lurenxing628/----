#!/usr/bin/env python3
"""Run the fast local development gate.

This script is intentionally smaller than scripts/run_quality_gate.py. It is a
push-time smoke gate for obvious mistakes, not the final clean proof.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from typing import Dict, List, Optional, Sequence, Tuple

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.daily_gate_scope import (
    ChangedPathSet,
    DailyGateScope,
    RuffPlan,
    plan_daily_gate_scope,
    pre_push_diff_paths,
    scanner_specs,
    with_local_changes,
)
from tools.long_gate_paths import GateContext, resolve_repo_root
from tools.quality_gate_shared import GateCheckSpec

# Every daily run includes these two real application contracts. If an impact
# target already includes their files, that execution also supplies the smoke proof.
FOCUSED_PYTEST_NODEIDS: Tuple[str, ...] = (
    "tests/app_runtime/test_launcher_startup.py::test_app_create_app_smoke",
    "tests/app_runtime/test_frontend_offline_static_assets.py::test_frontend_static_assets_are_offline_local",
)


def _gate_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _commands(
    required_targets: Sequence[str], ruff_plan: RuffPlan, specs: Sequence[GateCheckSpec]
) -> List[Tuple[str, List[str]]]:
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
    selected_scanners = set(ruff_plan.boundary_scanners)
    commands.extend(
        (spec.check_id, [sys.executable, *spec.args[1:]])
        for spec in specs
        if spec.check_id in selected_scanners
    )

    covered_files = {target for target in required_targets if "::" not in target}
    pytest_targets = list(required_targets)
    for nodeid in FOCUSED_PYTEST_NODEIDS:
        if nodeid not in pytest_targets and nodeid.split("::", 1)[0] not in covered_files:
            pytest_targets.append(nodeid)
    # One process and one collection; no xdist startup or repeated focused runs.
    commands.append(
        (
            "impact and focused pytest" if required_targets else "focused pytest",
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


def _failure_log_path(repo_root: str) -> Optional[str]:
    """失败日志落点：.git/aps-hook-cache 下单个固定文件，覆盖写、最多常驻一份、随 git 忽略隐身。

    任何解析/建目录异常都吞掉返回 None——失败日志只是排错便利，绝不能反过来影响门禁判定。
    """
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        common_dir = completed.stdout.strip()
        if completed.returncode != 0 or not common_dir:
            return None
        if not os.path.isabs(common_dir):
            common_dir = os.path.join(repo_root, common_dir)
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


def _run_step_streaming(repo_root: str, command: Sequence[str], env: Dict[str, str]) -> Tuple[int, str]:
    """跑一步命令：实时把输出转发到终端，同时捕获全文返回（供失败点名 + 落盘）。"""
    if sys.platform == "win32" and list(command[1:3]) == ["-m", "pytest"] and len(subprocess.list2cmdline(command)) >= 32767:
        # pytest reads one complete argument per line, preserving markers and paths with spaces.
        with tempfile.TemporaryDirectory(prefix="aps-pytest-args-") as argument_dir:
            argument_file = os.path.join(argument_dir, "pytest.args")
            with open(argument_file, "w", encoding="utf-8") as handle:
                handle.write("\n".join(command[3:]) + "\n")
            return _run_step_streaming(repo_root, [*command[:3], "@" + argument_file], env)
    process = subprocess.Popen(
        list(command),
        cwd=repo_root,
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


def _read_pre_push_scope(path: str) -> ChangedPathSet:
    """hook 写给目标 worktree 的范围文件（`daily_gate_scope_payload` 的形状）只在这里准入一次。"""
    with open(path, encoding="utf-8") as handle:
        scope = json.load(handle)
    if not isinstance(scope, dict) or type(scope.get("scope_known")) is not bool:
        raise ValueError("scope_known must be a boolean")
    paths = scope.get("changed_paths")
    if not isinstance(paths, list) or any(not isinstance(path, str) for path in paths):
        raise ValueError("changed_paths must be a list of strings")
    if not isinstance(scope.get("reason"), str):
        raise ValueError("reason must be a string")
    return ChangedPathSet(paths, scope["scope_known"], scope["reason"])


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the fast local development gate.")
    parser.add_argument("--pre-push-from-ref", default="")
    parser.add_argument("--pre-push-to-ref", default="")
    parser.add_argument("--pre-push-remote-name", default="")
    parser.add_argument("--pre-push-scope-file", default="", help=argparse.SUPPRESS)
    args = parser.parse_args(list(argv) if argv is not None else None)
    args.pre_push_scope = None
    if args.pre_push_scope_file:
        try:
            args.pre_push_scope = _read_pre_push_scope(args.pre_push_scope_file)
        except (OSError, ValueError) as exc:
            parser.error("cannot read --pre-push-scope-file: " + str(exc))
    return args


def daily_gate_scope_for_args(repo_root: str, args: argparse.Namespace, specs: Sequence[GateCheckSpec]) -> DailyGateScope:
    """本次运行的计划：本地未提交变更并上推送目标（hook 给的范围文件，或按 ref / 上游分支算出的差异）。"""
    target = (
        args.pre_push_scope
        if args.pre_push_scope is not None
        else pre_push_diff_paths(repo_root, args.pre_push_from_ref, args.pre_push_to_ref, args.pre_push_remote_name)
    )
    return plan_daily_gate_scope(repo_root, with_local_changes(repo_root, target), specs)


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
    ctx = GateContext(resolve_repo_root())
    specs = scanner_specs(ctx.repo_root)
    scope = daily_gate_scope_for_args(ctx.repo_root, args, specs)
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

    failure_log = _failure_log_path(ctx.repo_root)
    run_log: List[str] = []

    def _announce_failure_log() -> None:
        saved = _persist_failure_log(failure_log, run_log)
        if saved:
            print(f"[daily-fast-gate] 完整输出已留存：{saved}", file=sys.stderr, flush=True)

    commands = _commands(impact_plan.target_paths, ruff_plan, specs)
    for index, (label, command) in enumerate(commands, start=1):
        print(f"[daily-fast-gate] {index}/{len(commands)} {label}", flush=True)
        returncode, step_output = _run_step_streaming(ctx.repo_root, command, env)
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
