from __future__ import annotations

import os
import sys


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def main() -> None:
    repo_root = find_repo_root()
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)

    from web.bootstrap import factory as factory_mod

    cases = [
        (False, False, None, True, "非 debug 模式应注册退出备份"),
        (True, False, None, False, "源码 debug 父进程不应注册退出备份"),
        (True, False, "true", True, "源码 debug 子进程应注册退出备份"),
        (True, True, None, True, "frozen 模式即使 debug 也不走 reloader，应注册退出备份"),
    ]
    for debug, frozen, run_main, expected, label in cases:
        got = factory_mod._should_register_exit_backup(debug=debug, frozen=frozen, run_main=run_main)
        if got is not expected:
            raise RuntimeError(f"{label}：期望 {expected!r}，实际 {got!r}")

    print("OK")


if __name__ == "__main__":
    main()
