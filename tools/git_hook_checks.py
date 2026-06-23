#!/usr/bin/env python3
"""Small repository-local checks used by git hooks."""
from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, NamedTuple, Optional, Sequence, TextIO, Tuple

try:
    from tools import git_hook_cache
    from tools.git_hook_blocked_paths import BLOCKED_PATH_RULES, GENERIC_COMMIT_SUBJECTS
except ImportError:  # pragma: no cover - direct script execution path
    import git_hook_cache  # type: ignore[no-redef]
    from git_hook_blocked_paths import BLOCKED_PATH_RULES, GENERIC_COMMIT_SUBJECTS  # type: ignore[no-redef]

REPO_ROOT = Path(__file__).resolve().parents[1]
ZERO_SHA = "0" * 40
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
    if any(token in pattern for token in ("*", "?", "[")):
        return fnmatch.fnmatchcase(path, pattern)
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


class PrePushRef(NamedTuple):
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str


class PrePushInput(NamedTuple):
    refs: List[PrePushRef]
    saw_push_input: bool


def _pre_push_input_from_stdin(stream: Optional[TextIO] = None) -> PrePushInput:
    source: TextIO = stream if stream is not None else sys.stdin
    try:
        is_tty = bool(getattr(source, "isatty", lambda: True)())
    except Exception:
        is_tty = True
    if is_tty:
        return PrePushInput([], False)
    try:
        text = str(source.read() or "")
    except (AttributeError, OSError, ValueError):
        return PrePushInput([], False)
    refs: List[PrePushRef] = []
    saw_push_input = False
    for raw_line in text.splitlines():
        parts = raw_line.rsplit(maxsplit=3)
        if len(parts) != 4:
            continue
        saw_push_input = True
        local_ref, local_sha, remote_ref, remote_sha = parts
        if local_sha == ZERO_SHA:
            continue
        refs.append(PrePushRef(local_ref, local_sha, remote_ref, remote_sha))
    return PrePushInput(
        sorted(dict.fromkeys(refs), key=lambda item: (item.remote_ref, item.local_ref, item.local_sha, item.remote_sha)),
        saw_push_input,
    )


def _pre_push_refs_from_stdin(stream: Optional[TextIO] = None) -> List[PrePushRef]:
    return _pre_push_input_from_stdin(stream).refs


def _remote_refs_from_stdin(stream: Optional[TextIO] = None) -> List[str]:
    return sorted(dict.fromkeys(ref.remote_ref for ref in _pre_push_refs_from_stdin(stream) if ref.remote_ref))


def _pre_commit_input_from_env(env: Optional[Dict[str, str]] = None) -> PrePushInput:
    source = env if env is not None else os.environ
    from_ref = str(source.get("PRE_COMMIT_FROM_REF") or "").strip()
    to_ref = str(source.get("PRE_COMMIT_TO_REF") or "").strip()
    local_ref = str(source.get("PRE_COMMIT_LOCAL_BRANCH") or "").strip()
    remote_ref = str(source.get("PRE_COMMIT_REMOTE_BRANCH") or "").strip()
    if not to_ref:
        return PrePushInput([], False)
    if to_ref == ZERO_SHA:
        return PrePushInput([], True)
    return PrePushInput([PrePushRef(local_ref, to_ref, remote_ref, from_ref)], True)


def _pre_push_input_for_hook(stream: Optional[TextIO] = None) -> PrePushInput:
    env_input = _pre_commit_input_from_env()
    if env_input.saw_push_input:
        return env_input
    return _pre_push_input_from_stdin(stream)


def _pre_push_contexts_payload(refs: Sequence[PrePushRef]) -> List[Dict[str, str]]:
    return [
        {
            "local_ref": ref.local_ref,
            "local_sha": ref.local_sha,
            "remote_ref": ref.remote_ref,
            "remote_sha": ref.remote_sha,
        }
        for ref in refs
    ]


def _daily_gate_module():
    repo_root = str(REPO_ROOT)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from scripts import run_daily_quality_gate

    return run_daily_quality_gate


def _daily_scope_for_refs(refs: Sequence[PrePushRef], *, remote_name: str) -> Dict[str, Any]:
    daily_gate = _daily_gate_module()
    if not refs:
        scope = daily_gate.build_daily_gate_scope()
        return daily_gate.daily_gate_scope_payload(scope)
    if len(refs) == 1:
        ref = refs[0]
        scope = daily_gate.build_daily_gate_scope(
            pre_push_from_ref=ref.remote_sha,
            pre_push_to_ref=ref.local_sha,
            pre_push_remote_name=remote_name,
            pre_push_remote_ref=ref.remote_ref,
        )
        return daily_gate.daily_gate_scope_payload(scope)

    changed_paths: List[str] = []
    reasons: List[str] = []
    scope_known = True
    for ref in refs:
        changed = daily_gate._pre_push_diff_paths(
            ref.remote_sha,
            ref.local_sha,
            remote_name,
            remote_ref=ref.remote_ref,
        )
        changed_paths.extend(changed.paths)
        if changed.reason:
            reasons.append(changed.reason)
        if not changed.scope_known:
            scope_known = False
    if scope_known:
        scope = daily_gate.build_daily_gate_scope(
            pre_push_changed_paths=daily_gate._dedupe_paths(changed_paths),
            pre_push_scope_reason="multi-ref pre-push: " + "; ".join(sorted(dict.fromkeys(reasons))),
        )
    else:
        scope = daily_gate.build_daily_gate_scope(
            pre_push_from_ref="",
            pre_push_to_ref="missing-multi-ref-range",
            pre_push_remote_name=remote_name,
            pre_push_remote_ref=",".join(sorted(dict.fromkeys(ref.remote_ref for ref in refs))),
        )
    return daily_gate.daily_gate_scope_payload(scope)


def _daily_gate_command_for_refs(executable: str, refs: Sequence[PrePushRef], *, remote_name: str) -> List[str]:
    command = [executable, "scripts/run_daily_quality_gate.py"]
    if not refs:
        return command
    if len(refs) == 1:
        ref = refs[0]
        command.extend(
            [
                "--pre-push-from-ref",
                ref.remote_sha,
                "--pre-push-to-ref",
                ref.local_sha,
                "--pre-push-remote-name",
                remote_name,
                "--pre-push-remote-ref",
                ref.remote_ref,
            ]
        )
        return command

    daily_gate = _daily_gate_module()
    changed_paths: List[str] = []
    reasons: List[str] = []
    scope_known = True
    for ref in refs:
        changed = daily_gate._pre_push_diff_paths(
            ref.remote_sha,
            ref.local_sha,
            remote_name,
            remote_ref=ref.remote_ref,
        )
        changed_paths.extend(changed.paths)
        if changed.reason:
            reasons.append(changed.reason)
        if not changed.scope_known:
            scope_known = False
    if not scope_known:
        command.extend(
            [
                "--pre-push-from-ref",
                "",
                "--pre-push-to-ref",
                "missing-multi-ref-range",
                "--pre-push-remote-name",
                remote_name,
                "--pre-push-remote-ref",
                ",".join(sorted(dict.fromkeys(ref.remote_ref for ref in refs))),
            ]
        )
        return command
    for path in daily_gate._dedupe_paths(changed_paths):
        command.extend(["--pre-push-changed-path", path])
    command.extend(["--pre-push-scope-reason", "multi-ref pre-push: " + "; ".join(sorted(dict.fromkeys(reasons)))])
    return command


def _warn_dead_code_islands(executable: str) -> None:
    """warn-only 早警：打印死代码孤岛回潮报告，绝不影响 pre-push 门禁成败。

    扫描器自身永远 return 0；这里再包一层 try/except 兜底，确保即使调用失败也不阻断推送。
    """
    scanner = os.path.join(str(REPO_ROOT), "tools", "scan_dead_code_islands.py")
    if not os.path.isfile(scanner):
        return
    try:
        subprocess.call([executable, scanner], cwd=str(REPO_ROOT), env=_quality_gate_env())
    except Exception as exc:  # warn-only：连调用失败都不拦推送
        print(f"[dead-code-islands] 跳过（调用失败，不拦）：{exc}", flush=True)


def run_quality_gate(args: argparse.Namespace) -> int:
    try:
        executable = _project_python_executable()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    remote_name = str(getattr(args, "remote_name", "") or os.environ.get("PRE_COMMIT_REMOTE_NAME") or "")
    pre_push_input = _pre_push_input_for_hook()
    refs = pre_push_input.refs
    if pre_push_input.saw_push_input and not refs:
        print("[git-hook-cache] pre-push daily gate: no local ref to validate, skipped", flush=True)
        return 0
    remote_ref = str(getattr(args, "remote_ref", "") or "")
    if not remote_ref:
        remote_ref = ",".join(sorted(dict.fromkeys(ref.remote_ref for ref in refs if ref.remote_ref)))
    scope_payload = _daily_scope_for_refs(refs, remote_name=remote_name)
    ref_contexts = _pre_push_contexts_payload(refs)
    try:
        if git_hook_cache.pre_push_daily_cache_hit(
            executable,
            remote_name=remote_name,
            remote_ref=remote_ref,
            scope_payload=scope_payload,
            ref_contexts=ref_contexts,
        ):
            print(
                "[git-hook-cache] pre-push daily gate: reuse passed cache for unchanged tree and impact scope",
                flush=True,
            )
            return 0
    except git_hook_cache.HookCacheError as exc:
        print(f"[git-hook-cache] pre-push daily gate cache unavailable: {exc}", flush=True)

    # 树有变化（未命中缓存）才扫——正是可能冒出新死代码孤岛的时机；warn-only，不影响下方返回码。
    _warn_dead_code_islands(executable)

    command = _daily_gate_command_for_refs(executable, refs, remote_name=remote_name)
    returncode = subprocess.call(command, cwd=str(REPO_ROOT), env=_quality_gate_env())
    if int(returncode) == 0:
        try:
            git_hook_cache.write_pre_push_daily_cache(
                executable,
                remote_name=remote_name,
                remote_ref=remote_ref,
                scope_payload=scope_payload,
                ref_contexts=ref_contexts,
            )
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
