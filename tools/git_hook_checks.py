#!/usr/bin/env python3
"""Small repository-local checks used by git hooks."""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional, Sequence, TextIO, Tuple

if __name__ == "__main__":
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.workbench.node_runtime import NodeRuntimeError
from tools import git_hook_cache
from tools.daily_gate_scope import (
    ZERO_SHA,
    ChangedPathSet,
    branch_diff_paths,
    daily_gate_scope_payload,
    plan_daily_gate_scope,
    pre_push_diff_paths,
    scanner_specs,
    with_local_changes,
)
from tools.git_hook_blocked_paths import BLOCKED_PATH_RULES, GENERIC_COMMIT_SUBJECTS
from tools.long_gate_fingerprint import resolve_cached_esbuild_platform, resolve_cached_node_runtime
from tools.long_gate_paths import resolve_repo_root
from tools.long_gate_schema import decode_nul_paths

_GIT_REPOSITORY_LOCAL_ENV_KEYS: Tuple[str, ...] = (
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_CONFIG",
    "GIT_CONFIG_PARAMETERS",
    "GIT_CONFIG_COUNT",
    "GIT_OBJECT_DIRECTORY",
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_IMPLICIT_WORK_TREE",
    "GIT_GRAFT_FILE",
    "GIT_INDEX_FILE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_REPLACE_REF_BASE",
    "GIT_PREFIX",
    "GIT_SHALLOW_FILE",
    "GIT_COMMON_DIR",
)


def _run_git_bytes(repo_root: Path, args: Sequence[str]) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = bytes(result.stderr or b"").decode("utf-8", errors="replace").strip()
        raise SystemExit(stderr or "git command failed")
    return bytes(result.stdout or b"")


def _staged_paths(repo_root: Path) -> List[str]:
    return decode_nul_paths(
        _run_git_bytes(repo_root, ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"])
    )


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
    for path in paths:
        for pattern, reason in BLOCKED_PATH_RULES:
            if _path_matches_rule(path, pattern):
                blocked.append((path, reason))
                break
    return blocked


def check_staged_artifacts(repo_root: Path, _args: argparse.Namespace) -> int:
    blocked = _blocked_paths(_staged_paths(repo_root))
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


def check_commit_msg(_repo_root: Path, args: argparse.Namespace) -> int:
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


def _quality_gate_env() -> Dict[str, str]:
    env = git_hook_cache.hook_env()
    # Git 会把当前仓库的 GIT_DIR/GIT_WORK_TREE 等变量传给 hooks。若继续传给
    # pytest，测试里创建的临时 Git 仓库会误操作外层真实仓库，linked worktree
    # 尤其容易把 core.bare/user.* 等配置写回主仓库。
    for key in _GIT_REPOSITORY_LOCAL_ENV_KEYS:
        env.pop(key, None)
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


def _pre_push_input_for_hook(stream: Optional[TextIO] = None) -> PrePushInput:
    input_file = os.environ.get("APS_PRE_PUSH_INPUT_FILE")
    if input_file:
        try:
            with open(input_file, encoding="utf-8") as handle:
                return _pre_push_input_from_stdin(handle)
        except OSError as exc:
            raise RuntimeError(f"读取本次 Git pre-push 原始输入失败：{exc}") from exc
    if any(os.environ.get(key) for key in (
        "PRE_COMMIT_REMOTE_NAME", "PRE_COMMIT_REMOTE_URL", "PRE_COMMIT_REMOTE_BRANCH",
        "PRE_COMMIT_LOCAL_BRANCH", "PRE_COMMIT_FROM_REF", "PRE_COMMIT_TO_REF",
    )):
        raise RuntimeError(
            "pre-push 缺少完整 Git 原始输入。请用项目 .venv 的 Python 运行 tools/install_git_hooks.py 更新 hook。"
        )
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


def _daily_scope_for_refs(repo_root: Path, refs: Sequence[PrePushRef], *, remote_name: str) -> Dict[str, Any]:
    """与日常门禁 CLI 同一套计划机制：没有推送 ref 时取本地变更加上游差异，有 ref 时只取各目标提交的差异。"""
    root = str(repo_root)
    if not refs:
        changed = with_local_changes(root, branch_diff_paths(root))
    else:
        changed_paths: List[str] = []
        reasons: List[str] = []
        scope_known = True
        for ref in refs:
            ref_changed = pre_push_diff_paths(root, ref.remote_sha, ref.local_sha, remote_name)
            changed_paths.extend(ref_changed.paths)
            if ref_changed.reason:
                reasons.append(ref_changed.reason)
            if not ref_changed.scope_known:
                scope_known = False
        # 推送范围属于已提交目标，当前 checkout 的 dirty 内容不进入目标范围。
        changed = ChangedPathSet(
            sorted(dict.fromkeys(changed_paths)), scope_known, "; ".join(sorted(dict.fromkeys(reasons)))
        )
    return daily_gate_scope_payload(plan_daily_gate_scope(root, changed, scanner_specs(root)))


def _daily_gate_command(executable: str, *, scope_file: str = "") -> List[str]:
    command = [executable, "scripts/run_daily_quality_gate.py"]
    if scope_file:
        return [*command, "--pre-push-scope-file", scope_file]
    return command


def _provision_worktree_esbuild_vendor(
    source_root: Path, worktree: Path, *, environment: Mapping[str, str]
) -> None:
    """按目标 worktree 的 manifest 先验宿主 vendor，复制进 worktree 后再验一次目标。"""
    manifest_path = worktree / "scripts/workbench/esbuild-manifest.json"
    if not manifest_path.is_file():
        return
    from scripts.workbench.vendor_react import (
        load_esbuild_manifest,
        verify_esbuild_vendor,
    )

    try:
        node_rt = resolve_cached_node_runtime(environment)
    except NodeRuntimeError:
        node_rt = None
    try:
        manifest = load_esbuild_manifest(manifest_path)
        host_platform = resolve_cached_esbuild_platform(node_rt, environment)
        verified = verify_esbuild_vendor(
            source_root, manifest, host_platform=host_platform, target_platform=host_platform
        )
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(
            f"宿主缺少或损坏固定版本 esbuild vendor（{exc}）。"
            "请先运行 `python scripts/workbench/vendor_react.py --install-esbuild` 后重试。"
        ) from exc
    for rel_dir in ("vendor/node_modules/esbuild", f"vendor/node_modules/@esbuild/{verified['platform']}"):
        dest = worktree / rel_dir
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_root / rel_dir, dest, dirs_exist_ok=True)
    try:
        verify_esbuild_vendor(worktree, manifest, host_platform=host_platform, target_platform=verified["platform"])
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"预置 worktree esbuild vendor 复核失败：{exc}") from exc


def _run_target_daily_gate(
    repo_root: Path,
    executable: str,
    refs: Sequence[PrePushRef],
    *,
    remote_name: str,
    gate_env: Mapping[str, str],
) -> int:
    local_sha = refs[0].local_sha
    targets = ", ".join(sorted(dict.fromkeys(ref.remote_ref or ref.local_ref for ref in refs)))
    with tempfile.TemporaryDirectory(prefix="aps-pre-push-target-") as target_dir:
        worktree = Path(target_dir) / "worktree"
        scope_file = Path(target_dir) / "scope.json"
        scope_file.write_text(
            json.dumps(_daily_scope_for_refs(repo_root, refs, remote_name=remote_name), ensure_ascii=False),
            encoding="utf-8",
        )
        _run_git_bytes(repo_root, ["worktree", "add", "--detach", str(worktree), local_sha])
        try:
            _provision_worktree_esbuild_vendor(repo_root, worktree, environment=gate_env)
            print(f"[git-hook] daily gate target: {targets} ({local_sha})", flush=True)
            returncode = int(subprocess.call(
                _daily_gate_command(executable, scope_file=str(scope_file)),
                cwd=str(worktree), env=gate_env,
            ))
            if returncode:
                print(f"[git-hook] daily gate failed: {targets} ({local_sha}), exit={returncode}", file=sys.stderr)
            return returncode
        finally:
            _run_git_bytes(repo_root, ["worktree", "remove", "--force", str(worktree)])


def run_quality_gate(repo_root: Path, args: argparse.Namespace) -> int:
    try:
        executable = project_python_executable(repo_root)
        pre_push_input = _pre_push_input_for_hook()
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    remote_name = args.remote_name or os.environ.get("PRE_COMMIT_REMOTE_NAME", "")
    refs = pre_push_input.refs
    if pre_push_input.saw_push_input and not refs:
        print("[git-hook-cache] pre-push daily gate: no local ref to validate, skipped", flush=True)
        return 0
    remote_ref = args.remote_ref or ",".join(sorted(dict.fromkeys(ref.remote_ref for ref in refs if ref.remote_ref)))
    scope_payload = _daily_scope_for_refs(repo_root, refs, remote_name=remote_name)
    ref_contexts = _pre_push_contexts_payload(refs)
    gate_env = _quality_gate_env()
    daily_cache_key = None
    try:
        daily_cache_key = git_hook_cache.daily_gate_cache_key(
            repo_root, executable, remote_name=remote_name, remote_ref=remote_ref,
            scope_payload=scope_payload, ref_contexts=ref_contexts, env=gate_env,
        )
        if git_hook_cache.pre_push_daily_cache_hit(
            repo_root, executable, remote_name=remote_name, remote_ref=remote_ref,
            scope_payload=scope_payload, ref_contexts=ref_contexts, key_payload=daily_cache_key,
        ):
            print(
                "[git-hook-cache] pre-push daily gate: reuse passed cache for unchanged tree and impact scope",
                flush=True,
            )
            return 0
    except git_hook_cache.HookCacheError as exc:
        print(f"[git-hook-cache] pre-push daily gate cache unavailable: {exc}", flush=True)
        daily_cache_key = None

    if refs:
        refs_by_sha: Dict[str, List[PrePushRef]] = {}
        for ref in refs:
            refs_by_sha.setdefault(ref.local_sha, []).append(ref)
        returncode = 0
        try:
            for local_sha in sorted(refs_by_sha):
                returncode = _run_target_daily_gate(
                    repo_root, executable, refs_by_sha[local_sha], remote_name=remote_name, gate_env=gate_env
                )
                if returncode:
                    return returncode
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
    else:
        command = _daily_gate_command(executable)
        returncode = subprocess.call(command, cwd=str(repo_root), env=gate_env)
    if int(returncode) == 0 and daily_cache_key is not None:
        try:
            git_hook_cache.write_pre_push_daily_cache(
                repo_root, executable, remote_name=remote_name, remote_ref=remote_ref,
                scope_payload=scope_payload, ref_contexts=ref_contexts, key_payload=daily_cache_key,
            )
        except git_hook_cache.HookCacheError as exc:
            print(f"[git-hook-cache] pre-push daily gate cache write skipped: {exc}", flush=True)
    return int(returncode)


def run_final_quality_gate(repo_root: Path, _args: argparse.Namespace) -> int:
    try:
        executable = project_python_executable(repo_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    command = [
        executable,
        "scripts/run_quality_gate.py",
        "--require-clean-worktree",
        "--long-gate-cache",
    ]
    return subprocess.call(command, cwd=str(repo_root), env=_quality_gate_env())


def run_fast_static_precheck(repo_root: Path, _args: argparse.Namespace) -> int:
    try:
        executable = project_python_executable(repo_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    command = [executable, "scripts/run_quality_gate.py", "--fast-precheck"]
    return subprocess.call(command, cwd=str(repo_root), env=_quality_gate_env())


def run_ruff(repo_root: Path, _args: argparse.Namespace) -> int:
    try:
        executable = project_python_executable(repo_root)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    try:
        return git_hook_cache.run_staged_ruff(repo_root, executable)
    except git_hook_cache.HookCacheError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def _same_executable_path(left: str, right: str) -> bool:
    return os.path.normcase(os.path.realpath(str(left or ""))) == os.path.normcase(os.path.realpath(str(right or "")))


def ensure_project_python_runtime(repo_root: Path) -> None:
    executable = project_python_executable(repo_root)
    if _same_executable_path(sys.executable, executable):
        return
    os.execv(executable, [executable, *sys.argv])


def project_python_executable(repo_root: Path) -> str:
    if os.name == "nt":
        candidates = [
            repo_root / ".venv" / "Scripts" / "python.exe",
            repo_root / ".venv" / "bin" / "python",
        ]
    else:
        candidates = [
            repo_root / ".venv" / "bin" / "python",
            repo_root / ".venv" / "Scripts" / "python.exe",
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
    final_quality_gate_if_needed.set_defaults(func=run_final_quality_gate)

    fast_precheck = subparsers.add_parser("run-fast-static-precheck")
    fast_precheck.set_defaults(func=run_fast_static_precheck)

    ruff = subparsers.add_parser("run-ruff")
    ruff.set_defaults(func=run_ruff)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(Path(resolve_repo_root()), args))


if __name__ == "__main__":
    raise SystemExit(main())
