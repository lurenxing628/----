"""回归测试：factory._should_register_exit_backup 在四种场景下的注册判定——非 debug 注册；源码 debug 父进程（无 WERKZEUG_RUN_MAIN）不注册以避免 reloader 重复；源码 debug 子进程（run_main=true）注册；frozen 模式即使 debug 也不走 reloader 故注册。"""

from __future__ import annotations


def test_exit_backup_reloader_parent_skip() -> None:

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
