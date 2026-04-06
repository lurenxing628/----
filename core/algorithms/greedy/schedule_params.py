from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector
from core.services.common.field_parse import parse_field_float

from ..dispatch_rules import DispatchRule, parse_dispatch_rule
from ..sort_strategies import SortStrategy, parse_strategy
from .algo_stats import increment_counter
from .config_adapter import read_critical_schedule_config, read_schedule_config_value
from .date_parsers import parse_date, parse_datetime


@dataclass
class ScheduleParams:
    base_time: datetime
    end_dt_exclusive: Optional[datetime]
    strategy: SortStrategy
    used_params: Dict[str, Any]
    dispatch_mode_key: str
    dispatch_rule_enum: DispatchRule
    auto_assign_enabled: bool
    warnings: List[str]


def resolve_schedule_params(
    *,
    config: Any,
    strategy: Optional[SortStrategy],
    strategy_params: Optional[Dict[str, Any]],
    start_dt: Any,
    end_date: Any,
    dispatch_mode: Optional[str],
    dispatch_rule: Optional[str],
    resource_pool: Optional[Dict[str, Any]],
    algo_stats: Any = None,
    strict_mode: bool = False,
) -> ScheduleParams:
    warnings: List[str] = []

    def _critical_config_read(key: str, default: Any) -> tuple[Any, bool]:
        read_result = read_critical_schedule_config(config, key, default)
        if read_result.error is None:
            return read_result.value, bool(read_result.missing)
        increment_counter(algo_stats, f"{key}_read_failed_count", bucket="param_fallbacks")
        detail = str(read_result.error)
        if strict_mode:
            raise ValidationError(f"{key} 配置读取失败：{detail}", field=key)
        warnings.append(f"{key} 配置读取失败，已回退为 {default!r}：{detail}")
        return default, True

    base_time = start_dt or datetime.now()
    if base_time is not None and not isinstance(base_time, datetime):
        parsed = parse_datetime(base_time)
        if parsed is not None:
            base_time = parsed
            increment_counter(algo_stats, "start_dt_parsed_count", bucket="param_fallbacks")
            warnings.append(f"start_dt 非 datetime，已解析为 {base_time.strftime('%Y-%m-%d %H:%M:%S')}。")
        else:
            warnings.append(f"start_dt 无法解析，已忽略并使用当前时间：{start_dt!r}")
            increment_counter(algo_stats, "start_dt_default_now_count", bucket="param_fallbacks")
            base_time = datetime.now()

    end_d = parse_date(end_date)
    if end_date is not None and end_d is None:
        s0 = str(end_date).strip()
        if s0:
            warnings.append(f"end_date 无法解析，已忽略（不启用排产截止窗口）：{end_date!r}")
            increment_counter(algo_stats, "end_date_ignored_count", bucket="param_fallbacks")
    end_dt_exclusive: Optional[datetime] = None
    if end_d:
        end_dt_exclusive = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0) + timedelta(days=1)

    if strategy is None:
        strategy_key, strategy_missing = _critical_config_read("sort_strategy", "priority_first")
        strategy = SortStrategy.PRIORITY_FIRST
        try:
            valid_strategy_values = {s.value for s in SortStrategy}
            if not strategy_missing:
                if isinstance(strategy_key, SortStrategy):
                    raw_s = strategy_key.value
                else:
                    raw_s = str("" if strategy_key is None else strategy_key).strip().lower()
                if raw_s == "":
                    if strict_mode:
                        raise ValidationError("sort_strategy 不能为空", field="sort_strategy")
                    warnings.append(f"sort_strategy 为空，已回退为 {strategy.value}：{strategy_key!r}")
                    increment_counter(algo_stats, "sort_strategy_defaulted_count", bucket="param_fallbacks")
                elif raw_s not in valid_strategy_values:
                    if strict_mode:
                        raise ValidationError(
                            f"sort_strategy 不合法：{strategy_key!r}（允许值：priority_first / due_date_first / weighted / fifo）",
                            field="sort_strategy",
                        )
                    warnings.append(f"sort_strategy 非法，已回退为 {strategy.value}：{strategy_key!r}")
                    increment_counter(algo_stats, "sort_strategy_defaulted_count", bucket="param_fallbacks")
                else:
                    strategy = parse_strategy(strategy_key, default=SortStrategy.PRIORITY_FIRST)
        except ValidationError:
            raise
        except Exception:
            pass

    used_params: Dict[str, Any] = {}

    def _weighted_config_value(key: str, default: float) -> Any:
        read_result = read_schedule_config_value(config, key, default)
        if read_result.error is None:
            return default if read_result.missing else read_result.value
        detail = str(read_result.error)
        if strict_mode:
            raise ValidationError(f"{key} 配置读取失败：{detail}", field=key)
        warnings.append(f"{key} 配置读取失败，已回退为 {default!r}：{detail}")
        increment_counter(algo_stats, f"weighted_{key}_defaulted_count", bucket="param_fallbacks")
        return default

    def _weighted_value(raw_value: Any, key: str, default: float) -> float:
        collector = DegradationCollector()
        parsed = parse_field_float(
            raw_value,
            field=key,
            strict_mode=bool(strict_mode),
            scope="schedule_params.weighted",
            fallback=float(default),
            collector=collector,
            min_value=0.0,
        )
        if collector:
            increment_counter(algo_stats, f"weighted_{key}_defaulted_count", bucket="param_fallbacks")
        return float(parsed)

    if strategy == SortStrategy.WEIGHTED:
        if strategy_params is not None:
            sp = strategy_params if isinstance(strategy_params, dict) else {}
            used_params = {
                "priority_weight": _weighted_value(sp.get("priority_weight", 0.4), "priority_weight", 0.4),
                "due_weight": _weighted_value(sp.get("due_weight", 0.5), "due_weight", 0.5),
            }
        elif config is not None:
            used_params = {
                "priority_weight": _weighted_value(_weighted_config_value("priority_weight", 0.4), "priority_weight", 0.4),
                "due_weight": _weighted_value(_weighted_config_value("due_weight", 0.5), "due_weight", 0.5),
            }
        else:
            used_params = {"priority_weight": 0.4, "due_weight": 0.5}
    else:
        used_params = dict(strategy_params or {})

    dispatch_mode_from_config = dispatch_mode is None
    dispatch_mode_missing = False
    if dispatch_mode is None:
        dispatch_mode, dispatch_mode_missing = _critical_config_read("dispatch_mode", "batch_order")
    dispatch_mode_raw = dispatch_mode

    dispatch_mode_key = str("" if dispatch_mode is None else dispatch_mode).strip().lower()
    if dispatch_mode_missing:
        dispatch_mode_key = "batch_order"
    elif dispatch_mode_key == "":
        if dispatch_mode_from_config:
            if strict_mode:
                raise ValidationError("dispatch_mode 不能为空", field="dispatch_mode")
            warnings.append(f"dispatch_mode 为空，已回退为 batch_order：{dispatch_mode_raw!r}")
            increment_counter(algo_stats, "dispatch_mode_defaulted_count", bucket="param_fallbacks")
        dispatch_mode_key = "batch_order"
    if dispatch_mode_key not in ("batch_order", "sgs"):
        if strict_mode:
            raise ValidationError(
                f"dispatch_mode 不合法：{dispatch_mode_raw!r}（允许值：batch_order / sgs）",
                field="dispatch_mode",
            )
        warnings.append(f"dispatch_mode 非法，已回退为 batch_order：{dispatch_mode_raw!r}")
        increment_counter(algo_stats, "dispatch_mode_defaulted_count", bucket="param_fallbacks")
        dispatch_mode_key = "batch_order"

    dispatch_rule_from_config = dispatch_rule is None
    dispatch_rule_missing = False
    if dispatch_rule is None:
        dispatch_rule, dispatch_rule_missing = _critical_config_read("dispatch_rule", "slack")
    try:
        if isinstance(dispatch_rule, DispatchRule):
            raw_rule_key = dispatch_rule.value
            raw_rule_value = dispatch_rule.value
        else:
            raw_rule_value = dispatch_rule
            raw_rule_key = str("" if dispatch_rule is None else dispatch_rule).strip().lower()
    except Exception:
        raw_rule_value = dispatch_rule
        raw_rule_key = ""

    if dispatch_rule_missing:
        raw_rule_key = DispatchRule.SLACK.value
    elif dispatch_rule_from_config and raw_rule_key == "":
        if strict_mode:
            raise ValidationError("dispatch_rule 不能为空", field="dispatch_rule")
        warnings.append(f"dispatch_rule 为空，已回退为 {DispatchRule.SLACK.value}：{raw_rule_value!r}")
        increment_counter(algo_stats, "dispatch_rule_defaulted_count", bucket="param_fallbacks")
        raw_rule_key = DispatchRule.SLACK.value

    dispatch_rule_enum = parse_dispatch_rule(dispatch_rule, default=DispatchRule.SLACK)
    if strict_mode and raw_rule_key and raw_rule_key not in {r.value for r in DispatchRule}:
        raise ValidationError(
            f"dispatch_rule 不合法：{raw_rule_value!r}（允许值：slack / cr / atc）",
            field="dispatch_rule",
        )
    if raw_rule_key and raw_rule_key not in {r.value for r in DispatchRule}:
        warnings.append(f"dispatch_rule 非法，已回退为 {dispatch_rule_enum.value}：{raw_rule_value!r}")
        increment_counter(algo_stats, "dispatch_rule_defaulted_count", bucket="param_fallbacks")

    auto_assign_enabled = False
    raw, auto_assign_missing = _critical_config_read("auto_assign_enabled", "no")
    v = str("" if raw is None else raw).strip().lower()
    true_vals = ("yes", "y", "true", "1", "on")
    false_vals = ("no", "n", "false", "0", "off")

    if auto_assign_missing:
        v = "no"
    elif v == "":
        if strict_mode:
            raise ValidationError("auto_assign_enabled 不能为空", field="auto_assign_enabled")
        warnings.append(f"auto_assign_enabled 为空，已按 no 处理：{raw!r}")
        increment_counter(algo_stats, "auto_assign_enabled_defaulted_count", bucket="param_fallbacks")
        v = "no"

    auto_assign_enabled = v in true_vals
    if strict_mode and v not in true_vals and v not in false_vals:
        raise ValidationError(
            f"auto_assign_enabled 不合法：{raw!r}（允许值：yes / no）",
            field="auto_assign_enabled",
        )
    if v not in true_vals and v not in false_vals:
        warnings.append(f"auto_assign_enabled 非法，已按 no 处理：{raw!r}")
        increment_counter(algo_stats, "auto_assign_enabled_defaulted_count", bucket="param_fallbacks")

    if auto_assign_enabled and resource_pool is None:
        warnings.append("auto_assign_enabled=yes 但未提供 resource_pool：内部工序缺省资源将无法自动分配。")

    used_params["dispatch_mode"] = dispatch_mode_key
    used_params["dispatch_rule"] = dispatch_rule_enum.value
    used_params["auto_assign_enabled"] = "yes" if auto_assign_enabled else "no"

    return ScheduleParams(
        base_time=base_time,
        end_dt_exclusive=end_dt_exclusive,
        strategy=strategy,
        used_params=used_params,
        dispatch_mode_key=dispatch_mode_key,
        dispatch_rule_enum=dispatch_rule_enum,
        auto_assign_enabled=auto_assign_enabled,
        warnings=warnings,
    )

