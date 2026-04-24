from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector
from core.services.common.field_parse import parse_field_float
from core.services.common.strict_parse import parse_required_float
from core.services.scheduler.degradation_messages import public_degradation_event_message

from ..dispatch_rules import DispatchRule
from ..sort_strategies import SortStrategy
from .algo_stats import increment_counter
from .date_parsers import parse_date, parse_datetime

_FIELD_LABELS = {
    "config_snapshot": "运行期配置快照",
    "start_dt": "开始时间",
    "end_date": "截止日期",
    "sort_strategy": "排序策略",
    "dispatch_mode": "派工方式",
    "dispatch_rule": "派工规则",
    "strategy_params": "策略参数",
    "priority_weight": "优先级权重",
    "due_weight": "交期权重",
    "auto_assign_enabled": "自动分配",
}


def _field_label(field: str) -> str:
    return _FIELD_LABELS.get(str(field).strip(), str(field).strip() or "配置项")


def _public_field_degradation_message(*, code: str, field: str) -> str:
    message = public_degradation_event_message(code)
    if not message:
        return ""
    field_key = str(field or "").strip()
    if not field_key:
        return message
    return f"{field_key}（{_field_label(field_key)}）：{message}"


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


def _snapshot_attr(snapshot: Any, key: str) -> Any:
    label = _field_label(key)
    if snapshot is None:
        raise ValidationError("缺少运行期配置快照。", field="config_snapshot")
    if not hasattr(snapshot, key):
        raise ValidationError(f"运行期配置缺少“{label}”字段。", field=key)
    try:
        return getattr(snapshot, key)
    except Exception as exc:
        raise ValidationError(f"读取运行期配置中的“{label}”失败。", field=key) from exc


def _require_choice(raw_value: Any, *, field: str, valid_values: set[str]) -> str:
    label = _field_label(field)
    text = str("" if raw_value is None else raw_value).strip().lower()
    if not text:
        raise ValidationError(f"“{label}”不能为空。", field=field)
    if text not in valid_values:
        raise ValidationError(f"“{label}”配置无效，请返回排产参数页重新选择。", field=field)
    return text


def _require_weight(raw_value: Any, key: str) -> float:
    return float(parse_required_float(raw_value, field=key, min_value=0.0))


def _require_strategy_params_dict(strategy_params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if isinstance(strategy_params, dict):
        return strategy_params
    raise ValidationError("“策略参数”必须是字典。", field="strategy_params")


def _config_default_for(key: str) -> Any:
    from core.services.scheduler.config.config_field_spec import default_for

    return default_for(key)


def _build_runtime_snapshot(config: Any, *, strict_mode: bool) -> Any:
    from core.services.scheduler.config.config_snapshot import ensure_schedule_config_snapshot

    return ensure_schedule_config_snapshot(
        config,
        strict_mode=bool(strict_mode),
        source="schedule_params.runtime_config",
    )


def _validate_runtime_field(config: Any, field: str) -> None:
    from core.services.scheduler.config.config_field_spec import MISSING_POLICY_ERROR
    from core.services.scheduler.config.config_snapshot import coerce_runtime_config_field

    coerce_runtime_config_field(
        config,
        field,
        strict_mode=True,
        source="schedule_params.runtime_config",
        collector=DegradationCollector(),
        missing_policy=MISSING_POLICY_ERROR,
    )


def _weighted_override_value(
    raw_value: Any,
    key: str,
    *,
    strict_mode: bool,
    warnings: List[str],
    algo_stats: Any,
) -> float:
    collector = DegradationCollector()
    fallback = float(_config_default_for(key))
    value = parse_field_float(
        raw_value,
        field=key,
        strict_mode=bool(strict_mode),
        scope="schedule_params.weighted_strategy_params",
        fallback=fallback,
        collector=collector,
        min_value=0.0,
    )
    for event in collector.to_list():
        code = str(event.code or "").strip()
        message = _public_field_degradation_message(code=code, field=key)
        if message:
            warnings.append(message)
        increment_counter(
            algo_stats,
            f"weighted_{key}_defaulted_count",
            amount=int(event.count),
            bucket="param_fallbacks",
        )
    return float(value)


def _weighted_strategy_params(
    source: Dict[str, Any],
    *,
    strict_mode: bool,
    warnings: List[str],
    algo_stats: Any,
) -> Dict[str, Any]:
    missing = [key for key in ("priority_weight", "due_weight") if key not in source]
    if missing:
        missing_key = missing[0]
        raise ValidationError(f"加权策略参数缺少“{_field_label(missing_key)}”。", field=missing_key)
    return {
        "priority_weight": _weighted_override_value(
            source.get("priority_weight"),
            "priority_weight",
            strict_mode=bool(strict_mode),
            warnings=warnings,
            algo_stats=algo_stats,
        ),
        "due_weight": _weighted_override_value(
            source.get("due_weight"),
            "due_weight",
            strict_mode=bool(strict_mode),
            warnings=warnings,
            algo_stats=algo_stats,
        ),
    }


def _require_yes_no(raw_value: Any, *, field: str) -> str:
    label = _field_label(field)
    text = str("" if raw_value is None else raw_value).strip().lower()
    if text not in {"yes", "no"}:
        raise ValidationError(f"“{label}”配置无效，请返回排产参数页重新选择“是”或“否”。", field=field)
    return text


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
    runtime_snapshot = None
    snapshot_degradation_seen = set()

    def _runtime_snapshot() -> Any:
        nonlocal runtime_snapshot
        if runtime_snapshot is None:
            try:
                runtime_snapshot = _build_runtime_snapshot(config, strict_mode=False)
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError(
                    "构建运行期配置快照失败，请检查排产参数配置。",
                    field="config_snapshot",
                ) from exc
        return runtime_snapshot

    def _record_snapshot_degradations(field: str, *, counter_key: str) -> None:
        snapshot = _runtime_snapshot()
        for event in getattr(snapshot, "degradation_events", ()) or ():
            if not isinstance(event, dict):
                continue
            if str(event.get("field") or "").strip() != field:
                continue
            code = str(event.get("code") or "").strip()
            marker = (
                code,
                field,
            )
            if marker in snapshot_degradation_seen:
                continue
            snapshot_degradation_seen.add(marker)
            message = _public_field_degradation_message(code=code, field=field)
            if message:
                warnings.append(message)
            increment_counter(
                algo_stats,
                counter_key,
                amount=int(event.get("count") or 1),
                bucket="param_fallbacks",
            )

    def _snapshot_value(field: str, *, counter_key: str) -> Any:
        snapshot = _runtime_snapshot()
        if strict_mode:
            _validate_runtime_field(config, field)
        value = _snapshot_attr(snapshot, field)
        _record_snapshot_degradations(field, counter_key=counter_key)
        return value

    base_time = start_dt or datetime.now()
    if base_time is not None and not isinstance(base_time, datetime):
        parsed = parse_datetime(base_time)
        if parsed is not None:
            base_time = parsed
            increment_counter(algo_stats, "start_dt_parsed_count", bucket="param_fallbacks")
            warnings.append(f"开始时间已规范化为：{base_time.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            if strict_mode:
                raise ValidationError("“开始时间”格式不合法。", field="start_dt")
            warnings.append(f"开始时间无法解析，已忽略：{start_dt!r}")
            increment_counter(algo_stats, "start_dt_default_now_count", bucket="param_fallbacks")
            base_time = datetime.now()

    end_d = parse_date(end_date)
    if end_date is not None and end_d is None:
        text = str(end_date).strip()
        if text:
            if strict_mode:
                raise ValidationError("“截止日期”格式不合法。", field="end_date")
            warnings.append(f"截止日期无法解析，已忽略：{end_date!r}")
            increment_counter(algo_stats, "end_date_ignored_count", bucket="param_fallbacks")
    end_dt_exclusive: Optional[datetime] = None
    if end_d:
        end_dt_exclusive = datetime(end_d.year, end_d.month, end_d.day, 0, 0, 0) + timedelta(days=1)

    if strategy is None:
        strategy_key = _require_choice(
            _snapshot_value("sort_strategy", counter_key="sort_strategy_defaulted_count"),
            field="sort_strategy",
            valid_values={item.value for item in SortStrategy},
        )
        strategy = SortStrategy(strategy_key)

    used_params: Dict[str, Any]

    if strategy == SortStrategy.WEIGHTED:
        if strategy_params is not None:
            used_params = _weighted_strategy_params(
                _require_strategy_params_dict(strategy_params),
                strict_mode=bool(strict_mode),
                warnings=warnings,
                algo_stats=algo_stats,
            )
        else:
            used_params = {
                "priority_weight": _require_weight(
                    _snapshot_value("priority_weight", counter_key="weighted_priority_weight_defaulted_count"),
                    "priority_weight",
                ),
                "due_weight": _require_weight(
                    _snapshot_value("due_weight", counter_key="weighted_due_weight_defaulted_count"),
                    "due_weight",
                ),
            }
    else:
        used_params = dict(strategy_params or {})

    if dispatch_mode is None:
        dispatch_mode = _snapshot_value("dispatch_mode", counter_key="dispatch_mode_defaulted_count")
    dispatch_mode_key = _require_choice(
        dispatch_mode,
        field="dispatch_mode",
        valid_values={"batch_order", "sgs"},
    )

    if dispatch_rule is None:
        dispatch_rule = _snapshot_value("dispatch_rule", counter_key="dispatch_rule_defaulted_count")
    dispatch_rule_key = _require_choice(
        dispatch_rule,
        field="dispatch_rule",
        valid_values={item.value for item in DispatchRule},
    )
    dispatch_rule_enum = DispatchRule(dispatch_rule_key)

    auto_assign_enabled = _require_yes_no(
        _snapshot_value("auto_assign_enabled", counter_key="auto_assign_enabled_defaulted_count"),
        field="auto_assign_enabled",
    ) == "yes"

    if auto_assign_enabled and resource_pool is None:
        warnings.append("自动分配已启用，但资源池缺失，内部工序无法自动分配设备或人员。")

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
