from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable, List, Optional, Tuple, Union

from .priority_constants import PRIORITY_RANK, PRIORITY_WEIGHT, normalize_priority


class DispatchRule(Enum):
    """
    就绪集合（eligible set）派工规则（Serial SGS）。

    约定：返回的 key 为“越小越好”（可直接用于 min()）。
    """

    SLACK = "slack"  # 余量（越小越紧急）
    CR = "cr"  # critical ratio（越小越紧急）
    ATC = "atc"  # apparent tardiness cost（越大越紧急；这里用 -ATC 变成越小越好）


# ATC 的 k 是“看多远的交期”：k 越小越像 EDD，k 越大越像 WSPT。默认值不变；
# 梯子只给优化器搜索，用户配置页仍只在三条规则之间选。
DEFAULT_ATC_K = 2.0
ATC_K_LADDER: Tuple[float, ...] = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0)


def _finite_positive(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


@dataclass(frozen=True)
class DispatchRuleSpec:
    """一条可解码的派工规则及其数值旋钮；``token`` 是它唯一的文本形式。"""

    rule: DispatchRule
    atc_k: float = DEFAULT_ATC_K

    def __post_init__(self) -> None:
        if not isinstance(self.rule, DispatchRule):
            raise ValueError("dispatch rule spec requires a DispatchRule")
        if isinstance(self.atc_k, bool) or not isinstance(self.atc_k, (int, float)):
            raise ValueError("ATC k must be a number")
        k = _finite_positive(self.atc_k)
        if k is None:
            raise ValueError("ATC k must be a finite positive number")
        if self.rule is not DispatchRule.ATC and k != DEFAULT_ATC_K:
            raise ValueError("only the atc rule takes a k parameter")
        object.__setattr__(self, "atc_k", k)

    @property
    def token(self) -> str:
        if self.rule is DispatchRule.ATC and self.atc_k != DEFAULT_ATC_K:
            return f"{self.rule.value}:k={self.atc_k!r}"
        return self.rule.value


def parse_dispatch_rule_token(text: Any) -> DispatchRuleSpec:
    """接受 ``slack`` / ``cr`` / ``atc`` / ``atc:k=<正数>``；其余一律报错，不猜。"""
    raw = str("" if text is None else text).strip().lower()
    base, separator, params = raw.partition(":")
    try:
        rule = DispatchRule(base)
    except ValueError:
        raise ValueError(f"unknown dispatch rule token: {raw!r}") from None
    if not separator:
        return DispatchRuleSpec(rule)
    name, equals, value = params.partition("=")
    if rule is not DispatchRule.ATC or name.strip() != "k" or not equals:
        raise ValueError(f"unsupported dispatch rule parameter: {raw!r}")
    k = _finite_positive(value.strip())
    if k is None:
        raise ValueError(f"ATC k must be a finite positive number: {raw!r}")
    return DispatchRuleSpec(rule, k)


def as_dispatch_rule_spec(value: Union[DispatchRule, DispatchRuleSpec, str]) -> DispatchRuleSpec:
    """Normalize the three explicit contract forms; unknown text or other types fail loudly."""
    if isinstance(value, DispatchRuleSpec):
        return value
    if isinstance(value, DispatchRule):
        return DispatchRuleSpec(value)
    if isinstance(value, str):
        return parse_dispatch_rule_token(value)
    raise TypeError(f"unsupported dispatch rule value: {type(value).__name__}")


def dispatch_rule_search_pool(valid_rules: Iterable[Any]) -> Tuple[str, ...]:
    """优化器可搜的规则池：注册表规则在前，允许 atc 时再按离默认值的远近追加 k 梯子。"""
    out: List[str] = []
    for item in valid_rules:
        token = parse_dispatch_rule_token(item).token
        if token not in out:
            out.append(token)
    if DispatchRule.ATC.value in out:
        for k in sorted(ATC_K_LADDER, key=lambda value: (abs(math.log(value / DEFAULT_ATC_K)), value)):
            token = DispatchRuleSpec(DispatchRule.ATC, k).token
            if token not in out:
                out.append(token)
    return tuple(out)


@dataclass(frozen=True)
class DispatchInputs:
    rule: DispatchRule
    priority: str
    proc_hours: float
    avg_proc_hours: float
    # tie-break
    changeover_penalty: int  # 0=同族/不换型，1=换型（更差）
    batch_order: int
    seq: int
    op_id: int
    slack_hours: float
    time_left_hours: float
    atc_k: float = DEFAULT_ATC_K


def _safe_positive(value: float) -> float:
    # proc_hours <=0 时不能使用极小值兜底，否则 ATC 会出现极端值（错误地把不可估算候选排到最前）。
    # 同时过滤非有限值（NaN/Inf），避免出现 -0.0 / inf 传播导致的错误优先级。
    # 两项工时都是评分层算好的浮点数。
    number = float(value)
    if (not math.isfinite(number)) or number <= 0:
        return 0.0
    return number


def _weighted_urgency(value: float, weight: float) -> float:
    # Order-preserving priority scaling: a heavier batch looks tighter both while it still has room (divide)
    # and once it is late (multiply). weight 1.0 (normal) leaves the value untouched.
    return value / weight if value >= 0.0 else value * weight


def build_dispatch_key(inp: DispatchInputs) -> Tuple[float, ...]:
    """
    生成可排序 key（越小越优先）。

    说明：
    - primary：由 rule 决定；slack / CR 按优先级权重做保序缩放，ATC 本身带权重
    - tie-break：优先避免换型 -> 更高优先级 -> 更早交期 -> 更早开始 -> 更稳定批次顺序
    """
    pr = normalize_priority(inp.priority, default="normal")
    pr_rank = float(PRIORITY_RANK[pr])
    w = float(PRIORITY_WEIGHT[pr])

    slack_h, time_left_h = inp.slack_hours, inp.time_left_hours

    if inp.rule == DispatchRule.CR:
        p = _safe_positive(inp.proc_hours) or _safe_positive(inp.avg_proc_hours) or 1.0
        primary = _weighted_urgency(float(time_left_h / p), w)
    elif inp.rule == DispatchRule.ATC:
        avg_raw = _safe_positive(inp.avg_proc_hours)
        p = _safe_positive(inp.proc_hours) or avg_raw or 1.0
        avg_p = avg_raw or p
        # ATC 越大越优；这里用 -ATC 使其“越小越好”。k 来自已校验的规则规格。
        atc = (w / p) * math.exp((-max(slack_h, 0.0)) / (inp.atc_k * avg_p))
        primary = float(-atc)
    else:
        # SLACK
        primary = _weighted_urgency(float(slack_h), w)

    return (
        primary,
        float(inp.changeover_penalty),
        pr_rank,
        float(time_left_h),  # 越小越紧急
        float(inp.batch_order),
        float(inp.seq),
        float(inp.op_id),
    )
