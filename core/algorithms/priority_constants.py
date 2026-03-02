from __future__ import annotations

from typing import Any, Dict

DEFAULT_PRIORITY = "normal"

# 约定：越小越优先（critical > urgent > normal）
PRIORITY_RANK: Dict[str, int] = {"critical": 0, "urgent": 1, "normal": 2}
PRIORITY_ORDER = PRIORITY_RANK  # alias（排序策略使用 order 这个名字）

# 用于 ATC 等规则（越大越紧急）
PRIORITY_WEIGHT: Dict[str, float] = {"critical": 3.0, "urgent": 2.0, "normal": 1.0}

# 用于“权重混合”排序策略的离散分
PRIORITY_SCORE: Dict[str, int] = {"critical": 100, "urgent": 60, "normal": 20}


def normalize_priority(value: Any, *, default: str = DEFAULT_PRIORITY) -> str:
    """
    将 priority 规范化为 normal/urgent/critical（大小写/空白容错）。

    未知值回退到 default（default 若非法则回退到 DEFAULT_PRIORITY）。
    """
    d = str(default or DEFAULT_PRIORITY).strip().lower() or DEFAULT_PRIORITY
    if d not in PRIORITY_RANK:
        d = DEFAULT_PRIORITY

    s = str(value or "").strip().lower()
    if not s:
        return d
    return s if s in PRIORITY_RANK else d

