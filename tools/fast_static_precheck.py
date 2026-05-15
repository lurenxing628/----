#!/usr/bin/env python3
"""Fast static precheck for changed Python files.

This module is intentionally a small early-warning tool. It does not run the
formal full quality gate and it never writes long-gate success cache proof.
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence, Tuple

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

FAST_STATIC_PRECHECK_BANNER = "FAST STATIC PRECHECK ONLY: not final ruff/pyright/full quality gate proof"
NO_TARGETS_MESSAGE = "没有本次改动的 Python 文件需要快速静态预检"
PYRIGHT_SKIP_MESSAGE = (
    "FAST STATIC PRECHECK ONLY: pyright skipped by design. "
    "not pyright_gate_full, not pyright_tools_full."
)

SKIP_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "backups",
    "build",
    "dist",
    "evidence",
    "logs",
    "node_modules",
    "venv",
}
SKIP_PATH_PATTERNS = (
    "*.egg-info/*",
    "*.egg-info",
    "static/js/frappe-gantt*",
    "static/js/frappe-gantt*/*",
)


class FastStaticPrecheckError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangedPythonFiles:
    paths: Tuple[str, ...]
    sources: Dict[str, Tuple[str, ...]]


def normalize_repo_path(path: str, repo_root: str = REPO_ROOT) -> str:
    text = str(path or "").replace("\\", "/").strip()
    if not text:
        return ""
    if text.startswith("./"):
        text = text[2:]
    if os.path.isabs(text):
        try:
            text = os.path.relpath(os.path.realpath(text), os.path.realpath(repo_root))
        except ValueError:
            return ""
    normalized = os.path.normpath(text).replace("\\", "/")
    if normalized in {"", "."}:
        return ""
    if normalized == ".." or normalized.startswith("../") or os.path.isabs(normalized):
        return ""
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized


def _decode_nul_paths(output: bytes) -> List[str]:
    paths: List[str] = []
    for raw in bytes(output or b"").split(b"\0"):
        if not raw:
            continue
        paths.append(raw.decode("utf-8", errors="replace"))
    return paths


def _run_git_paths(args: Sequence[str], repo_root: str = REPO_ROOT) -> List[str]:
    command = ["git", *list(args)]
    result = subprocess.run(
        command,
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if int(result.returncode) != 0:
        stderr = bytes(result.stderr or b"").decode("utf-8", errors="replace").strip()
        stdout = bytes(result.stdout or b"").decode("utf-8", errors="replace").strip()
        detail = stderr or stdout or f"returncode={result.returncode}"
        raise FastStaticPrecheckError(f"无法收集本次改动文件：{' '.join(command)}: {detail}")
    return _decode_nul_paths(bytes(result.stdout or b""))


def collect_staged_paths(repo_root: str = REPO_ROOT) -> List[str]:
    return _run_git_paths(
        ["diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", "--"],
        repo_root=repo_root,
    )


def collect_unstaged_paths(repo_root: str = REPO_ROOT) -> List[str]:
    return _run_git_paths(
        ["diff", "--name-only", "--diff-filter=ACMR", "-z", "--"],
        repo_root=repo_root,
    )


def collect_untracked_paths(repo_root: str = REPO_ROOT) -> List[str]:
    return _run_git_paths(
        ["ls-files", "--others", "--exclude-standard", "-z", "--"],
        repo_root=repo_root,
    )


def collect_base_ref_paths(base_ref: str, repo_root: str = REPO_ROOT) -> List[str]:
    ref = str(base_ref or "").strip()
    if not ref:
        raise FastStaticPrecheckError("--base-ref 不能为空")
    return _run_git_paths(
        ["diff", "--name-only", "--diff-filter=ACMR", "-z", f"{ref}...HEAD", "--"],
        repo_root=repo_root,
    )


def _is_repo_local_file(rel_path: str, repo_root: str) -> bool:
    abs_path = os.path.join(repo_root, rel_path.replace("/", os.sep))
    if not os.path.isfile(abs_path):
        return False
    root = os.path.normcase(os.path.realpath(repo_root))
    real_path = os.path.normcase(os.path.realpath(abs_path))
    return real_path == root or real_path.startswith(root + os.sep)


def _should_skip_path(rel_path: str) -> bool:
    normalized = normalize_repo_path(rel_path)
    if not normalized:
        return True
    parts = [part for part in normalized.split("/") if part]
    if any(part in SKIP_DIR_NAMES for part in parts):
        return True
    for pattern in SKIP_PATH_PATTERNS:
        if fnmatch.fnmatch(normalized, pattern):
            return True
    return False


def filter_python_targets(paths: Sequence[str], repo_root: str = REPO_ROOT) -> Tuple[str, ...]:
    targets = []
    seen = set()
    for raw_path in list(paths or []):
        rel_path = normalize_repo_path(str(raw_path), repo_root=repo_root)
        if not rel_path or rel_path in seen:
            continue
        seen.add(rel_path)
        if not rel_path.endswith(".py"):
            continue
        if _should_skip_path(rel_path):
            continue
        if not _is_repo_local_file(rel_path, repo_root):
            continue
        targets.append(rel_path)
    return tuple(sorted(targets))


def _record_sources(source_map: Dict[str, List[str]], paths: Sequence[str], source: str, repo_root: str) -> None:
    for path in filter_python_targets(paths, repo_root=repo_root):
        source_map.setdefault(path, [])
        if source not in source_map[path]:
            source_map[path].append(source)


def collect_changed_python_files(
    repo_root: str = REPO_ROOT,
    *,
    include_staged: bool = True,
    include_unstaged: bool = True,
    include_untracked: bool = True,
    base_ref: str = "",
) -> ChangedPythonFiles:
    source_map: Dict[str, List[str]] = {}
    if base_ref:
        _record_sources(source_map, collect_base_ref_paths(base_ref, repo_root=repo_root), "base-ref", repo_root)
    else:
        if include_staged:
            _record_sources(source_map, collect_staged_paths(repo_root), "staged", repo_root)
        if include_unstaged:
            _record_sources(source_map, collect_unstaged_paths(repo_root), "unstaged", repo_root)
        if include_untracked:
            _record_sources(source_map, collect_untracked_paths(repo_root), "untracked", repo_root)
    paths = tuple(sorted(source_map))
    return ChangedPythonFiles(
        paths=paths,
        sources={path: tuple(source_map[path]) for path in paths},
    )


def _precheck_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def build_ruff_command(targets: Sequence[str]) -> List[str]:
    return [sys.executable, "-m", "ruff", "check", "--force-exclude", "--", *list(targets)]


def _copyable_command(command: Sequence[str]) -> str:
    return " ".join(shlex.quote(str(part)) for part in list(command or []))


def run_ruff(targets: Sequence[str], repo_root: str = REPO_ROOT) -> int:
    command = build_ruff_command(targets)
    print("[fast-static-precheck] ruff quick check:", _copyable_command(command), flush=True)
    return int(subprocess.call(command, cwd=repo_root, env=_precheck_env()))


def _print_scope_notice(base_ref: str) -> None:
    print(FAST_STATIC_PRECHECK_BANNER, flush=True)
    print("快速静态预检只用于提前提醒明显问题，不代表完整质量门禁通过。", flush=True)
    print("这是局部 ruff，不是 ruff_check_full；not ruff_check_full.", flush=True)
    print("pyright 默认跳过；不是 pyright_gate_full，也不是 pyright_tools_full。", flush=True)
    print(
        "最终收口仍需运行：PYTHONDONTWRITEBYTECODE=1 .venv/bin/python "
        "scripts/run_quality_gate.py --require-clean-worktree --long-gate-cache",
        flush=True,
    )
    if base_ref:
        print(
            f"base-ref 模式：只检查 {base_ref}...HEAD 的已提交差异，不纳入 unstaged / untracked。",
            flush=True,
        )


def _print_targets(changed: ChangedPythonFiles) -> None:
    print("[fast-static-precheck] target Python files:", flush=True)
    for path in changed.paths:
        sources = ", ".join(changed.sources.get(path, ()))
        print(f"- {path} ({sources})", flush=True)


def _parse_args(argv: Optional[Sequence[str]]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fast static precheck for changed Python files")
    parser.add_argument("--no-staged", action="store_true", help="do not include staged Python files")
    parser.add_argument("--no-unstaged", action="store_true", help="do not include unstaged tracked Python files")
    parser.add_argument("--no-untracked", action="store_true", help="do not include untracked Python files")
    parser.add_argument("--base-ref", default="", help="check committed diff from BASE_REF...HEAD instead of worktree changes")
    parser.add_argument("--print-targets", action="store_true", help="print target Python files before running ruff")
    return parser.parse_args(list(argv) if argv is not None else None)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    base_ref = str(args.base_ref or "").strip()
    _print_scope_notice(base_ref)
    try:
        changed = collect_changed_python_files(
            REPO_ROOT,
            include_staged=not bool(args.no_staged),
            include_unstaged=not bool(args.no_unstaged),
            include_untracked=not bool(args.no_untracked),
            base_ref=base_ref,
        )
    except FastStaticPrecheckError as exc:
        print(f"[fast-static-precheck] failed to collect files: {exc}", file=sys.stderr, flush=True)
        return 2

    if args.print_targets:
        _print_targets(changed)

    if not changed.paths:
        print(NO_TARGETS_MESSAGE, flush=True)
        print(PYRIGHT_SKIP_MESSAGE, flush=True)
        return 0

    returncode = run_ruff(changed.paths, REPO_ROOT)
    print(PYRIGHT_SKIP_MESSAGE, flush=True)
    if returncode != 0:
        print("[fast-static-precheck] failed: local ruff quick check failed.", file=sys.stderr, flush=True)
        print("可复制复跑命令：", _copyable_command(build_ruff_command(changed.paths)), file=sys.stderr, flush=True)
        return int(returncode)
    print("[fast-static-precheck] passed: local ruff quick check passed.", flush=True)
    print("注意：这不是完整质量门禁通过证明。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
