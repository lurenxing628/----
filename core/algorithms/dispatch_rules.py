from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional, Tuple

from .priority_constants import PRIORITY_RANK, PRIORITY_WEIGHT, normalize_priority


class DispatchRule(Enum):
    """
    就绪集合（eligible set）派工规则（Serial SGS）。

    约定：返回的 key 为“越小越好”（可直接用于 min()）。
    """

    SLACK = "slack"  # 余量（越小越紧急）
    CR = "cr"  # critical ratio（越小越紧急）
    ATC = "atc"  # apparent tardiness cost（越大越紧急；这里用 -ATC 变成越小越好）


def _due_end(d: Optional[date]) -> datetime:
    if not d:
        return datetime.max
    return datetime(d.year, d.month, d.day, 23, 59, 59)


def parse_dispatch_rule(value: Any, default: DispatchRule = DispatchRule.SLACK) -> DispatchRule:
    if isinstance(value, DispatchRule):
        return value
    try:
        # 容错：大小写/空白（例如 "CR" / " atc "）
        return DispatchRule(str(value).strip().lower())
    except Exception:
        return default


@dataclass(frozen=True)
class DispatchInputs:
    rule: DispatchRule
    priority: str
    due_date: Optional[date]
    est_start: datetime
    est_end: datetime
    proc_hours: float
    avg_proc_hours: float
    # tie-break
    changeover_penalty: int  # 0=同族/不换型，1=换型（更差）
    batch_order: int
    batch_id: str
    seq: int
    op_id: int


def build_dispatch_key(inp: DispatchInputs) -> Tuple[float, ...]:
    """
    生成可排序 key（越小越优先）。

    说明：
    - primary：由 rule 决定
    - tie-break：优先避免换型 -> 更高优先级 -> 更早交期 -> 更早开始 -> 更稳定批次顺序
    """
    pr = normalize_priority(inp.priority, default="normal")
    pr_rank = float(PRIORITY_RANK.get(pr, 99))
    w = float(PRIORITY_WEIGHT.get(pr, 1.0))

    due_end = _due_end(inp.due_date)
    slack_h = (due_end - inp.est_end).total_seconds() / 3600.0
    time_left_h = (due_end - inp.est_start).total_seconds() / 3600.0

    # proc_hours <=0（或无法解析）时不能使用极小值兜底，否则 ATC 会出现极端值（错误地把不可估算候选排到最前）。
    p: float
    try:
        ph = float(inp.proc_hours)
        p = ph if ph > 0 else 0.0
    except Exception:
        p = 0.0
    if not p or p <= 0:
        # 回退到平均处理时间尺度（若也不可用，再回退到 1h）
        try:
            aph = float(inp.avg_proc_hours)
            p = aph if aph > 0 else 1.0
        except Exception:
            p = 1.0

    avg_p: float
    try:
        aph2 = float(inp.avg_proc_hours)
        avg_p = aph2 if aph2 > 0 else p
    except Exception:
        avg_p = p

    if inp.rule == DispatchRule.CR:
        cr = time_left_h / p
        primary = float(cr)
    elif inp.rule == DispatchRule.ATC:
        # ATC 越大越优；这里用 -ATC 使其“越小越好”
        k = 2.0
        atc = (w / p) * math.exp((-max(slack_h, 0.0)) / (k * avg_p))
        primary = float(-atc)
    else:
        # SLACK
        primary = float(slack_h)

    return (
        primary,
        float(inp.changeover_penalty),
        pr_rank,
        float(time_left_h),  # 越小越紧急
        float(inp.batch_order),
        float(inp.seq),
        float(inp.op_id),
    )


def mean_positive(values: Dict[str, float]) -> float:
    """
    仅对严格为正（>0）的值取均值。

    说明：
    - 名称语义：positive => >0
    - 空/无正值返回 0.0
    """
    vals = []
    for v in values.values():
        if v is None:
            continue
        try:
            fv = float(v)
        except Exception:
            continue
        if fv > 0:
            vals.append(fv)
    if not vals:
        return 0.0
    return float(statistics.fmean(vals))

