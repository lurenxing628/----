from __future__ import annotations

from typing import Any, Dict

DEFAULT_PRIORITY = "normal"

# 约定：越小越优先（critical > urgent > normal）
PRIORITY_RANK: Dict[str, int] = {"critical": 0, "urgent": 1, "normal": 2}

# 用于 ATC 等规则（越大越紧急）
PRIORITY_WEIGHT: Dict[str, float] = {"critical": 3.0, "urgent": 2.0, "normal": 1.0}

# 用于“权重混合”排序策略的离散分
PRIORITY_SCORE: Dict[str, int] = {"critical": 100, "urgent": 60, "normal": 20}


def normalize_priority(value: Any, *, default: str = DEFAULT_PRIORITY) -> str:
    """
    将 priority 规范化为 normal/urgent/critical（大小写/空白容错）。

    未知值回退到 default（default 若非法则回退到 DEFAULT_PRIORITY）。
    """
    if isinstance(value, str) and value in PRIORITY_RANK:
        return value
    s = str(value or "").strip().lower()
    if s in PRIORITY_RANK:
        return s
    d = str(default or DEFAULT_PRIORITY).strip().lower() or DEFAULT_PRIORITY
    return d if d in PRIORITY_RANK else DEFAULT_PRIORITY


def priority_weight_scaled(value: Any, *, scale: int = 100, default: str = DEFAULT_PRIORITY) -> int:
    pr = normalize_priority(value, default=default)
    try:
        scale_i = max(1, int(scale))
    except Exception:
        scale_i = 100
    weight = PRIORITY_WEIGHT[pr]
    return int(round(weight * scale_i))
