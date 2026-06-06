"""回归测试：排序策略中文展示已收口到 presenter——strict_strategy_display_label 须把 priority_first/due_date_first/weighted/fifo 映射为「优先级优先/交期优先/综合优先级和交期/先进先出」；web_new_test 的 gantt.html 仍内联该 strategy_zh 映射，而已收口页面（batches.html、system/history.html）的模板里不得再出现 strategy_zh/status_zh/mode_zh 等本地状态映射。"""

import os

from web.viewmodels.scheduler_history_summary import strict_strategy_display_label

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_v2_strategy_zh_contract() -> None:
    repo_root = REPO_ROOT
    expected = {
        "priority_first": "优先级优先",
        "due_date_first": "交期优先",
        "weighted": "综合优先级和交期",
        "fifo": "先进先出",
    }
    for key, label in expected.items():
        if strict_strategy_display_label(key) != label:
            raise RuntimeError(f"策略展示 helper 映射错误：{key} -> {label}")

    gantt_files = [
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "gantt.html"),
    ]
    for path in gantt_files:
        text = _read(path)
        for key, label in expected.items():
            token = f"'{key}': '{label}'"
            if token not in text:
                raise RuntimeError(f"模板缺少 strategy_zh 映射：{os.path.relpath(path, repo_root)} -> {token}")

    presenter_owned_templates = [
        os.path.join(repo_root, "templates", "scheduler", "batches.html"),
        os.path.join(repo_root, "web_new_test", "templates", "scheduler", "batches.html"),
        os.path.join(repo_root, "templates", "system", "history.html"),
    ]
    for path in presenter_owned_templates:
        text = _read(path)
        for token in ("strategy_zh", "status_zh", "mode_zh", "status_zh.get", "strategy_zh.get", "mode_zh.get"):
            if token in text:
                raise RuntimeError(f"已收口页面不应继续在模板里维护本地状态映射：{os.path.relpath(path, repo_root)} -> {token}")
