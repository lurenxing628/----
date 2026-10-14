#!/usr/bin/env python3
"""Install the standard project hooks and wrap pre-push to preserve Git stdin."""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.git_hook_checks import _ensure_project_python_runtime, _project_python_executable

WRAPPER_MARKER = "# APS native pre-push input wrapper v1"
HOOK_TYPES = ("pre-commit", "commit-msg", "pre-push")


def _wrapper_content(executable: str) -> str:
    entry = str(REPO_ROOT / "tools" / "native_pre_push.py")
    return (
        "#!/bin/sh\n" + WRAPPER_MARKER + "\n"
        + f"exec {shlex.quote(executable)} {shlex.quote(entry)} \"$0\" \"$@\"\n"
    )


def main() -> int:
    _ensure_project_python_runtime()
    from pre_commit.commands.install_uninstall import is_our_script

    custom_paths = subprocess.run(
        ["git", "config", "--get", "core.hooksPath"], cwd=str(REPO_ROOT), capture_output=True,
    )
    if custom_paths.returncode == 0:
        print("当前仓库设置了 core.hooksPath，请先处理该安装位置后再安装项目 hooks。", file=sys.stderr)
        return 1
    common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"], cwd=str(REPO_ROOT), capture_output=True, text=True,
        check=True,
    )
    common_dir = Path(common.stdout.strip())
    if not common_dir.is_absolute():
        common_dir = REPO_ROOT / common_dir
    hooks_dir = common_dir / "hooks"
    push_hook = hooks_dir / "pre-push"
    chain = hooks_dir / "pre-push.pre-commit"
    ours = push_hook.is_file() and WRAPPER_MARKER in push_hook.read_text(encoding="utf-8", errors="replace")
    for hook_type in HOOK_TYPES:
        path = hooks_dir / hook_type
        if os.path.lexists(str(path)) and not (hook_type == "pre-push" and ours) and not is_our_script(str(path)):
            print(f"已有用户 hook，保留原文件，请先处理安装冲突：{path}", file=sys.stderr)
            return 1
    if os.path.lexists(str(chain)) and not is_our_script(str(chain)):
        print(f"已有非 pre-commit 底层脚本，保留原文件，请先处理安装冲突：{chain}", file=sys.stderr)
        return 1
    if ours and not chain.is_file():
        print(f"项目 pre-push 包装缺少原 pre-commit 链：{chain}", file=sys.stderr)
        return 1

    executable = _project_python_executable()
    original_wrapper = push_hook.read_bytes() if ours else None
    if ours:
        os.replace(str(chain), str(push_hook))
    returncode = subprocess.call([executable, "-m", "pre_commit", "install"], cwd=str(REPO_ROOT))
    if returncode:
        if original_wrapper is not None:
            os.replace(str(push_hook), str(chain))
            push_hook.write_bytes(original_wrapper)
            push_hook.chmod(0o755)
        return int(returncode)
    os.replace(str(push_hook), str(chain))
    push_hook.write_text(_wrapper_content(executable), encoding="utf-8")
    push_hook.chmod(0o755)
    print(f"APS pre-push wrapper installed at {push_hook}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
