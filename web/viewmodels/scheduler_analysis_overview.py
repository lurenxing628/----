from __future__ import annotations

from typing import Any, Dict


def build_analysis_labels() -> Dict[str, Dict[str, str]]:
    return {
        "strategy": {
            "priority_first": "优先级优先",
            "due_date_first": "交期优先",
            "weighted": "综合优先级和交期",
            "fifo": "先进先出",
            "improve": "优化排产",
            "greedy": "快速排产",
            "manual": "手动排产",
        },
        "status": {
            "success": "成功",
            "partial": "部分成功",
            "failed": "失败",
            "simulated": "模拟排产",
            "ok": "成功",
            "fail": "失败",
            "ok2": "成功",
        },
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
