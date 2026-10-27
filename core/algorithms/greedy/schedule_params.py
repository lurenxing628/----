from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Set

from core.algorithm_contracts.date_parsers import due_exclusive, parse_date
from core.algorithm_contracts.dispatch_rules import DispatchRuleSpec, parse_dispatch_rule_token
from core.algorithm_contracts.sort_strategies import SortStrategy
from core.errors import ValidationError
from core.models.schedule_config_runtime_snapshot import ScheduleConfigSnapshot
from core.shared.strict_parse import parse_required_float

_FIELD_LABELS = {
    "end_date": "截止日期",
    "sort_strategy": "排序策略",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "派工规则",
    "strategy_params": "策略参数",
    "priority_weight": "优先级权重",
    "due_weight": "交期权重",
    "ready_weight": "就绪权重",
    "auto_assign_enabled": "自动分配",
}


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(str(field).strip(), str(field).strip() or "配置项")


@dataclass
class ScheduleParams:
    base_time: datetime
    end_dt_exclusive: Optional[datetime]
    strategy: SortStrategy
    used_params: Dict[str, Any]
    dispatch_mode_key: str
    dispatch_rule_spec: DispatchRuleSpec
    auto_assign_enabled: bool
    warnings: List[str]


def _require_choice(raw_value: Any, *, field: str, valid_values: Set[str]) -> str:
    label = _field_label(field)
    text = str("" if raw_value is None else raw_value).strip().lower()
    if not text:
        raise ValidationError(f"“{label}”不能为空。", field=field)
    if text not in valid_values:
        raise ValidationError(f"“{label}”这项设置现在不能直接用，请返回排产参数页重新选择。", field=field)
    return text


def _require_weight(raw_value: Any, key: str) -> float:
    return float(parse_required_float(raw_value, field=key, min_value=0.0))


def _require_strategy_params_dict(strategy_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(strategy_params, dict):
        return strategy_params
    raise ValidationError("“策略参数”必须是字典。", field="strategy_params")


def _weighted_override_value(raw_value: Any, key: str) -> float:
    # 提示文案用中文标签，出错字段仍定位到参数键。
    try:
        return parse_required_float(raw_value, field=_field_label(key), min_value=0.0)
    except ValidationError as exc:
        raise ValidationError(exc.message, field=key) from exc


def _weighted_strategy_params(source: Dict[str, Any]) -> Dict[str, Any]:
    missing = [key for key in ("priority_weight", "due_weight") if key not in source]
    if missing:
        missing_key = missing[0]
        raise ValidationError(f"加权策略参数缺少“{_field_label(missing_key)}”。", field=missing_key)
    return {
        "priority_weight": _weighted_override_value(source["priority_weight"], "priority_weight"),
        "due_weight": _weighted_override_value(source["due_weight"], "due_weight"),
    }


def _require_yes_no(raw_value: Any, *, field: str) -> str:
    label = _field_label(field)
    text = str("" if raw_value is None else raw_value).strip().lower()
    if text not in {"yes", "no"}:
        raise ValidationError(f"“{label}”这项设置现在不能直接用，请返回排产参数页重新选择“是”或“否”。", field=field)
    return text


def _resolve_end_dt_exclusive(end_date: Any) -> Optional[datetime]:
    end_d = parse_date(end_date)
    if end_date is not None and end_d is None and str(end_date).strip():
        raise ValidationError("“截止日期”写法不对，请填写类似 2026-05-20 的日期。", field="end_date")
    if not end_d:
        return None
    # 复用 due_exclusive 的哨兵口径：9999-12-31（date.max 的日期）是 ERP 常见的
    # “无截止”哨兵值，裸 +1 天会溢出 OverflowError；due_exclusive 对该哨兵显式
    # 返回 datetime.max（语义“不设上限”），普通日期仍按当日 0 点 +1 天作排他上界。
    return due_exclusive(end_d)


def _resolve_strategy(strategy: Optional[SortStrategy], *, config: ScheduleConfigSnapshot) -> SortStrategy:
    if strategy is not None:
        return strategy
    strategy_key = _require_choice(
        config.sort_strategy,
        field="sort_strategy",
        valid_values={item.value for item in SortStrategy},
    )
    return SortStrategy(strategy_key)


def _runtime_weighted_params(config: ScheduleConfigSnapshot) -> Dict[str, Any]:
    return {
        "priority_weight": _require_weight(config.priority_weight, "priority_weight"),
        "due_weight": _require_weight(config.due_weight, "due_weight"),
    }


def _resolve_used_params(
    *,
    config: ScheduleConfigSnapshot,
    strategy: SortStrategy,
    strategy_params: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if strategy != SortStrategy.WEIGHTED:
        return dict(strategy_params or {})
    if strategy_params is not None:
        return _weighted_strategy_params(_require_strategy_params_dict(strategy_params))
    return _runtime_weighted_params(config)


def _resolve_dispatch_mode_key(dispatch_mode: Optional[str], *, config: ScheduleConfigSnapshot) -> str:
    return _require_choice(
        config.dispatch_mode if dispatch_mode is None else dispatch_mode,
        field="dispatch_mode",
        valid_values={"batch_order", "sgs"},
    )


def _resolve_dispatch_rule_spec(dispatch_rule: Optional[str], *, config: ScheduleConfigSnapshot) -> DispatchRuleSpec:
    resolved_rule = config.dispatch_rule if dispatch_rule is None else dispatch_rule
    label = _field_label("dispatch_rule")
    text = str("" if resolved_rule is None else resolved_rule).strip().lower()
    if not text:
        raise ValidationError(f"“{label}”不能为空。", field="dispatch_rule")
    try:
        # 配置页只给三条规则；优化器搜索时还会传带 k 参数的 atc 令牌，同一语法一处解析。
        return parse_dispatch_rule_token(text)
    except ValueError:
        raise ValidationError(f"“{label}”这项设置现在不能直接用，请返回排产参数页重新选择。", field="dispatch_rule") from None


def _resolve_auto_assign_enabled(config: ScheduleConfigSnapshot) -> bool:
    return _require_yes_no(config.auto_assign_enabled, field="auto_assign_enabled") == "yes"


def resolve_schedule_params(
    *,
    config: ScheduleConfigSnapshot,
    strategy: Optional[SortStrategy],
    strategy_params: Optional[Dict[str, Any]],
    start_dt: datetime,
    end_date: Any,
    dispatch_mode: Optional[str],
    dispatch_rule: Optional[str],
    resource_pool: Optional[Dict[str, Any]],
) -> ScheduleParams:
    warnings: List[str] = []

    end_dt_exclusive = _resolve_end_dt_exclusive(end_date)
    resolved_strategy = _resolve_strategy(strategy, config=config)
    used_params = _resolve_used_params(config=config, strategy=resolved_strategy, strategy_params=strategy_params)
    dispatch_mode_key = _resolve_dispatch_mode_key(dispatch_mode, config=config)
    dispatch_rule_spec = _resolve_dispatch_rule_spec(dispatch_rule, config=config)
    auto_assign_enabled = _resolve_auto_assign_enabled(config)

    if auto_assign_enabled and resource_pool is None:
        warnings.append("自动分配已启用，但可用设备或人员资料缺失，自制工序无法自动分配设备或人员。")

    used_params["dispatch_mode"] = dispatch_mode_key
    used_params["dispatch_rule"] = dispatch_rule_spec.token
    used_params["auto_assign_enabled"] = "yes" if auto_assign_enabled else "no"

    return ScheduleParams(
        base_time=start_dt,
        end_dt_exclusive=end_dt_exclusive,
        strategy=resolved_strategy,
        used_params=used_params,
        dispatch_mode_key=dispatch_mode_key,
        dispatch_rule_spec=dispatch_rule_spec,
        auto_assign_enabled=auto_assign_enabled,
        warnings=warnings,
    )
