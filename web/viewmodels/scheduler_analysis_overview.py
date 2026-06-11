from __future__ import annotations

from typing import Any, Dict

from .scheduler_history_summary import _STRATEGY_LABELS
from .scheduler_summary_result_state import result_status_display_labels


def build_analysis_labels() -> Dict[str, Dict[str, str]]:
    return {
        # strategy/status 从唯一字源派生（fusion-label-single-source）——
        # 别名（ok/fail）由 result_state 的 resolve 归一，不再当平行展示键
        "strategy": dict(_STRATEGY_LABELS),
        "status": result_status_display_labels(),
        "mode": {
            "improve": "优化模式",
            "greedy": "快速模式",
            "single": "单次排产",
        },
        "dispatch_mode": {
            "batch_order": "按批次顺序排",
            "sgs": "智能派工",
        },
        "dispatch_rule": {
            "slack": "时间余量少的先做",
            "cr": "交期更紧的先做",
            "atc": "综合紧急度优先",
        },
    }


def analysis_choice_label(value: Any, labels: Dict[str, str], *, empty_label: str = "-", invalid_label: str = "记录异常") -> str:
    text = str(value or "").strip()
    if not text:
        return empty_label
    return labels.get(text, invalid_label)


__all__ = ["analysis_choice_label", "build_analysis_labels"]
