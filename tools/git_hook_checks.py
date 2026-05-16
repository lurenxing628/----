#!/usr/bin/env python3
"""Small repository-local checks used by git hooks."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, TextIO, Tuple

try:
    from tools import git_hook_cache
except ImportError:  # pragma: no cover - direct script execution path
    import git_hook_cache  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[1]

BLOCKED_PATH_RULES: Tuple[Tuple[str, str], ...] = (
    (".DS_Store", "macOS 自动生成文件，提交后只会制造无意义 diff"),
    ("*/.DS_Store", "macOS 自动生成文件，提交后只会制造无意义 diff"),
    (".iris/", "本机 Codex/Iris 临时计划文件，不属于项目源码"),
    (".playwright-mcp/", "本地浏览器调试产物，不属于项目源码"),
    (".limcode_", "LimCode 本地中间产物，不属于本次提交边界"),
    ("logs/aps_port.txt", "APS 本地运行时端口文件，换机器后无意义"),
    ("logs/aps_host.txt", "APS 本地运行时地址文件，换机器后无意义"),
    ("logs/aps_db_path.txt", "APS 本地运行时数据库路径，换机器后无意义"),
    ("logs/aps_runtime.json", "APS 本地运行时状态，换机器后无意义"),
    ("logs/aps_runtime.lock", "APS 本地运行锁文件，提交后会干扰别人"),
    ("logs/aps_secret_key.txt", "APS 本地密钥文件，不能提交"),
    ("launcher.log", "APS 本地启动日志可能包含本机路径或错误明细，不能提交"),
    ("*/launcher.log", "APS 本地启动日志可能包含本机路径或错误明细，不能提交"),
    ("evidence/QualityGate/quality_gate_manifest.json", "质量门禁 proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/current_full_test_debt.json", "质量门禁债务快照是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/full_test_debt_summary.json", "full-test-debt summary 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/full_test_debt_node_cache.json", "full-test-debt nodeid 缓存是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/architecture_scan_cache.json", "architecture scan 文件级缓存是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/startup_runtime_regressions.json", "startup regressions proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/required_regressions.json", "required regressions proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/required_regressions/", "required regressions 分组 proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/debt_ledger_sync.json", "debt ledger sync proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/ruff_check_full.json", "ruff full proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/pyright_gate_full.json", "pyright gate proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/pyright_tools_full.json", "pyright tools proof 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/quickref_vs_routes.md", "quickref/routes 对账报告是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/receipts/", "质量门禁 receipts 是运行产物，应由当前门禁重新生成"),
    ("evidence/QualityGate/logs/", "质量门禁日志是运行产物，不应该混进普通提交"),
    ("evidence/QualityGate/long_gate/", "长耗时门禁缓存是本地运行产物，不应该混进普通提交"),
    ("evidence/QualityGate/collect_nodeids.json", "pytest collect nodeid 快照是运行产物，应由当前门禁重新生成"),
    ("evidence/FullSelfTest/pytest_tests_output.txt", "FullSelfTest 原始输出很重，应保留格式化报告而不是原始控制台输出"),
    ("aps_test.db", "本地测试数据库，不属于项目源码"),
    ("aps_test.db-", "本地测试数据库旁路文件，不属于项目源码"),
)

GENERIC_COMMIT_SUBJECTS = {
    "fix",
    "fix bug",
    "update",
    "change",
    "changes",
    "wip",
    "tmp",
    "temp",
    "debug",
    "修复",
    "更新",
    "修改",
    "提交",
    "改一下",
}


def _run_git(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or "git command failed")
    return result.stdout


def _staged_paths() -> List[str]:
    output = _run_git(["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    return [item for item in output.split("\0") if item]


def _normalize_path(path: str) -> str:
    return git_hook_cache.normalize_repo_path(path)


def _path_matches_rule(path: str, pattern: str) -> bool:
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if pattern.endswith("_"):
        return path.startswith(pattern)
    if pattern.startswith("*/"):
        return path.endswith(pattern[1:])
    if pattern.endswith("-"):
        return path == pattern[:-1] or path.startswith(pattern)
    return path == pattern


def _blocked_paths(paths: Iterable[str]) -> List[Tuple[str, str]]:
    blocked: List[Tuple[str, str]] = []
    for raw_path in paths:
        path = _normalize_path(raw_path)
        if not path:
            continue
        for pattern, reason in BLOCKED_PATH_RULES:
            if _path_matches_rule(path, pattern):
                blocked.append((path, reason))
                break
    return blocked


def check_staged_artifacts(_args: argparse.Namespace) -> int:
    blocked = _blocked_paths(_staged_paths())
    if not blocked:
        return 0

    print("提交里混入了本地临时文件或门禁运行产物，请先移出本次提交：", file=sys.stderr)
    for path, reason in blocked:
        print(f"- {path}: {reason}", file=sys.stderr)
    print("如果确实要提交这类文件，请先单独说明原因，并把对应提交边界讲清楚。", file=sys.stderr)
    return 1


def _meaningful_commit_lines(message: str) -> List[str]:
    lines: List[str] = []
    for raw_line in message.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def check_commit_msg(args: argparse.Namespace) -> int:
    message_path = Path(args.message_file)
    message = message_path.read_text(encoding="utf-8", errors="replace")
    lines = _meaningful_commit_lines(message)
    if not lines:
        print("提交说明是空的，请写清楚这次为什么改、改了什么、怎么验证。", file=sys.stderr)
        return 1

    subject = lines[0]
    lowered = subject.lower().strip()
    if lowered.startswith("merge ") or lowered.startswith("revert "):
        return 0

    if lowered in GENERIC_COMMIT_SUBJECTS or len(subject.replace(" ", "")) < 6:
        print("提交标题太泛了。请写成让以后回看的人能看懂的一句话。", file=sys.stderr)
        print("建议至少说清楚：为什么改、改了什么、影响是什么。", file=sys.stderr)
        return 1

    if len(lines) == 1:
        print("提醒：这个提交只有标题。重要改动建议补正文，写清楚背景、目的、影响和验证。", file=sys.stderr)
    return 0


def _quality_gate_env() -> dict:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.pop("APS_SKIP_QUALITY_GATE", None)
    return env


def _remote_refs_from_stdin(stream: Optional[TextIO] = None) -> List[str]:
    source: TextIO = stream if stream is not None else sys.stdin
    try:
        is_tty = bool(getattr(source, "isatty", lambda: True)())
    except Exception:
        is_tty = True
    if is_tty:
        return []
    try:
        text = str(source.read() or "")
    except (AttributeError, OSError, ValueError):
        return []
    refs: List[str] = []
    for raw_line in text.splitlines():
        parts = raw_line.split()
        if len(parts) >= 3 and parts[2]:
            refs.append(parts[2])
    return sorted(dict.fromkeys(refs))


def run_quality_gate(args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    remote_name = str(getattr(args, "remote_name", "") or "")
    remote_ref = str(getattr(args, "remote_ref", "") or "")
    if not remote_ref:
        remote_ref = ",".join(_remote_refs_from_stdin())
    try:
        if git_hook_cache.pre_push_daily_cache_hit(executable, remote_name=remote_name, remote_ref=remote_ref):
            print(
                "[git-hook-cache] pre-push daily gate: reuse passed cache for unchanged HEAD/tree",
                flush=True,
            )
            return 0
    except git_hook_cache.HookCacheError as exc:
        print(f"[git-hook-cache] pre-push daily gate cache unavailable: {exc}", flush=True)

    command = [executable, "scripts/run_daily_quality_gate.py"]
    returncode = subprocess.call(command, cwd=str(REPO_ROOT), env=_quality_gate_env())
    if int(returncode) == 0:
        try:
            git_hook_cache.write_pre_push_daily_cache(executable, remote_name=remote_name, remote_ref=remote_ref)
        except git_hook_cache.HookCacheError as exc:
            print(f"[git-hook-cache] pre-push daily gate cache write skipped: {exc}", flush=True)
    return int(returncode)


def run_final_quality_gate(_args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    command = [
        executable,
        "scripts/run_quality_gate.py",
        "--require-clean-worktree",
        "--long-gate-cache",
    ]
    return subprocess.call(command, cwd=str(REPO_ROOT), env=_quality_gate_env())


def run_final_quality_gate_if_needed(_args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        if git_hook_cache.final_gate_cache_hit(executable):
            print(
                "[git-hook-cache] final gate: same clean HEAD already has local final proof cache",
                flush=True,
            )
            return 0
    except git_hook_cache.HookCacheError as exc:
        print(f"[git-hook-cache] final gate cache unavailable: {exc}", flush=True)

    returncode = run_final_quality_gate(_args)
    if int(returncode) == 0:
        try:
            git_hook_cache.write_final_gate_cache(executable)
        except git_hook_cache.HookCacheError as exc:
            print(f"[git-hook-cache] final gate cache write skipped: {exc}", flush=True)
    return int(returncode)


def run_fast_static_precheck(_args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    command = [executable, "scripts/run_quality_gate.py", "--fast-precheck"]
    return subprocess.call(command, cwd=str(REPO_ROOT), env=_quality_gate_env())


def run_ruff(_args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        return git_hook_cache.run_staged_ruff(executable)
    except git_hook_cache.HookCacheError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _same_executable_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.realpath(str(left or ""))) == os.path.normcase(os.path.realpath(str(right or "")))


def _ensure_project_python_runtime() -> None:
    executable = _project_python_executable()
    if _same_executable_path(sys.executable, executable):
        return
    os.execv(executable, [executable, *sys.argv])


def _project_python_executable() -> str:
    if os.name == "nt":
        candidates = [
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
            REPO_ROOT / ".venv" / "bin" / "python",
        ]
    else:
        candidates = [
            REPO_ROOT / ".venv" / "bin" / "python",
            REPO_ROOT / ".venv" / "Scripts" / "python.exe",
        ]
    for python_path in candidates:
        if python_path.exists():
            return str(python_path)
    raise RuntimeError(
        "找不到项目 .venv 里的 Python。请先创建 .venv 并安装依赖，再运行本地 hook 或质量门禁。"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Repository git hook checks")
    subparsers = parser.add_subparsers(dest="command", required=True)

    staged = subparsers.add_parser("check-staged-artifacts")
    staged.set_defaults(func=check_staged_artifacts)

    commit_msg = subparsers.add_parser("check-commit-msg")
    commit_msg.add_argument("message_file")
    commit_msg.set_defaults(func=check_commit_msg)

    quality_gate = subparsers.add_parser("run-quality-gate")
    quality_gate.add_argument("remote_name", nargs="?", default="")
    quality_gate.add_argument("remote_url", nargs="?", default="")
    quality_gate.add_argument("--remote-ref", default="")
    quality_gate.set_defaults(func=run_quality_gate)

    final_quality_gate = subparsers.add_parser("run-final-quality-gate")
    final_quality_gate.set_defaults(func=run_final_quality_gate)

    final_quality_gate_if_needed = subparsers.add_parser("run-final-quality-gate-if-needed")
    final_quality_gate_if_needed.set_defaults(func=run_final_quality_gate_if_needed)

    fast_precheck = subparsers.add_parser("run-fast-static-precheck")
    fast_precheck.set_defaults(func=run_fast_static_precheck)

    ruff = subparsers.add_parser("run-ruff")
    ruff.set_defaults(func=run_ruff)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    if argv is None:
        _ensure_project_python_runtime()
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
