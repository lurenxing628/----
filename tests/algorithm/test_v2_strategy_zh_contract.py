"""回归测试：排序策略中文展示已收口到 presenter——strict_strategy_display_label 须把 priority_first/due_date_first/weighted/fifo 映射为「优先级优先/交期优先/综合优先级和交期/先进先出」；全部 9 个消费页的内联 strategy_zh/status_zh 已于 2026-06-12 收编（fusion-label-single-source，回潮守卫见 test_label_single_source_contract.py），已收口页面（batches.html、system/history.html）的模板里不得再出现 strategy_zh/status_zh/mode_zh 等本地状态映射。"""

import os

from tests._support.paths import REPO_ROOT_STR as REPO_ROOT
from web.viewmodels.scheduler_history_summary import strict_strategy_display_label


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def test_v2_strategy_zh_contract() -> None:
    expected = {
        "priority_first": "优先级优先",
        "due_date_first": "交期优先",
        "weighted": "综合优先级和交期",
        "fifo": "先进先出",
    }
    for key, label in expected.items():
        if strict_strategy_display_label(key) != label:
            raise RuntimeError(f"策略展示 helper 映射错误：{key} -> {label}")
