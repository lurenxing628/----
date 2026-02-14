from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from ..dispatch_rules import DispatchRule, parse_dispatch_rule
from ..sort_strategies import SortStrategy, parse_strategy
from .config_adapter import cfg_get


def parse_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("/", "-")
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        return None


def parse_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    s = s.replace("/", "-").replace("T", " ").replace("：", ":")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue
    try:
        return datetime.strptime(s, "%Y-%m-%d")
    except Exception:
        return None


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
    start_dt: Optional[datetime],
    end_date: Any,
    dispatch_mode: Optional[str],
    dispatch_rule: Optional[str],
    resource_pool: Optional[Dict[str, Any]],
) -> ScheduleParams:
    warnings: List[str] = []

    base_time = start_dt or datetime.now()
    if base_time is not None and not isinstance(base_time, datetime):
        parsed = parse_datetime(base_time)
        if parsed is not None:
            base_time = parsed
            warnings.append(f"start_dt 非 datetime，已解析为 {base_time.strftime('%Y-%m-%d %H:%M:%S')}。")
        else:
            warnings.append(f"start_dt 无法解析，已忽略并使用当前时间：{start_dt!r}")
            base_time = datetime.now()

    end_d = parse_date(end_date)
    if end_date is not None and end_d is None:
        s0 = str(end_date).strip()
        if s0:
            warnings.append(f"end_date 无法解析，已忽略（不启用排产截止窗口）：{end_date!r}")
    end_dt_exclusive: Optional[datetime] = None
    if end_d:
        end_dt_exclusive = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0) + timedelta(days=1)

    if strategy is None:
        try:
            strategy_key = cfg_get(config, "sort_strategy", "priority_first")
        except Exception:
            strategy_key = "priority_first"
        strategy = parse_strategy(strategy_key, default=SortStrategy.PRIORITY_FIRST)
        try:
            if isinstance(strategy_key, SortStrategy):
                raw_s = strategy_key.value
            else:
                raw_s = str(strategy_key or "").strip().lower()
            if raw_s and raw_s not in {s.value for s in SortStrategy}:
                warnings.append(f"sort_strategy 非法，已回退为 {strategy.value}：{strategy_key!r}")
        except Exception:
            pass

    used_params: Dict[str, Any] = {}
    if strategy == SortStrategy.WEIGHTED:
        if strategy_params is not None:

            def _safe_float(v: Any, default: float) -> float:
                try:
                    f = float(v)
                    return f if math.isfinite(f) else float(default)
                except Exception:
                    return float(default)

            sp = strategy_params if isinstance(strategy_params, dict) else {}
            used_params = {
                "priority_weight": _safe_float(sp.get("priority_weight", 0.4), 0.4),
                "due_weight": _safe_float(sp.get("due_weight", 0.5), 0.5),
            }
        elif config is not None:

            def _cfg_float(key: str, default: float) -> float:
                try:
                    f = float(cfg_get(config, key, default))
                    return f if math.isfinite(f) else float(default)
                except Exception:
                    return float(default)

            used_params = {
                "priority_weight": _cfg_float("priority_weight", 0.4),
                "due_weight": _cfg_float("due_weight", 0.5),
            }
        else:
            used_params = {"priority_weight": 0.4, "due_weight": 0.5}
    else:
        used_params = dict(strategy_params or {})

    if dispatch_mode is None and config is not None:
        try:
            dispatch_mode = str(cfg_get(config, "dispatch_mode", "batch_order"))
        except Exception:
            dispatch_mode = "batch_order"
    dispatch_mode_key = str(dispatch_mode or "batch_order").strip().lower() or "batch_order"
    if dispatch_mode_key not in ("batch_order", "sgs"):
        if dispatch_mode is not None and str(dispatch_mode).strip():
            warnings.append(f"dispatch_mode 非法，已回退为 batch_order：{dispatch_mode!r}")
        dispatch_mode_key = "batch_order"

    if dispatch_rule is None and config is not None:
        try:
            dispatch_rule = str(cfg_get(config, "dispatch_rule", "slack"))
        except Exception:
            dispatch_rule = "slack"
    try:
        if isinstance(dispatch_rule, DispatchRule):
            raw_rule_key = dispatch_rule.value
        else:
            raw_rule_key = str(dispatch_rule or "").strip().lower()
    except Exception:
        raw_rule_key = ""
    dispatch_rule_enum = parse_dispatch_rule(dispatch_rule, default=DispatchRule.SLACK)
    if raw_rule_key and raw_rule_key not in {r.value for r in DispatchRule}:
        warnings.append(f"dispatch_rule 非法，已回退为 {dispatch_rule_enum.value}：{dispatch_rule!r}")

    auto_assign_enabled = False
    if config is not None:
        try:
            raw = cfg_get(config, "auto_assign_enabled", "no")
            v = str(raw or "").strip().lower()
            true_vals = ("yes", "y", "true", "1", "on")
            false_vals = ("no", "n", "false", "0", "off", "")
            auto_assign_enabled = v in true_vals
            if v not in true_vals and v not in false_vals:
                warnings.append(f"auto_assign_enabled 非法，已按 no 处理：{raw!r}")
        except Exception:
            auto_assign_enabled = False
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

