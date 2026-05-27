#!/usr/bin/env python3
"""Scan Python files changed by the APS three-gap roadmap for Python 3.8 risk."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Optional, Sequence

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from tools import scan_py38plus_syntax  # noqa: E402

DEFAULT_BASE_REF = "d4589d77"


def _git_changed_python_files(base_ref: str, root: str) -> List[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", str(base_ref), "--", "*.py"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        raise RuntimeError((proc.stderr or proc.stdout or "git diff failed").strip())
    paths = []
    for line in proc.stdout.splitlines():
        rel_path = scan_py38plus_syntax.normalize_repo_path(line)
        if rel_path.endswith(".py") and os.path.isfile(os.path.join(root, rel_path)):
            paths.append(rel_path)
    return sorted(dict.fromkeys(paths))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="扫描 APS 三个差距 roadmap 起点以来改过的 Python 文件，确保 Python 3.8 兼容。"
    )
    parser.add_argument("--base-ref", default=DEFAULT_BASE_REF, help="roadmap 起点提交，默认 d4589d77。")
    parser.add_argument("--root", default=REPO_ROOT, help="仓库根目录。")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_arg_parser().parse_args(argv)
    root = os.path.abspath(args.root)
    paths = _git_changed_python_files(str(args.base_ref), root)
    result = scan_py38plus_syntax.scan_paths(root, paths, include_annotation_runtime=True)
    print(scan_py38plus_syntax.format_text_report(result, max_examples=50))
    if result.findings:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
