from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import (
    DegradationCollector,
    DegradationEvent,
    degradation_events_to_dicts,
)

from .config_field_spec import (
    MISSING_POLICY_ERROR,
    MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
    coerce_config_field,
    default_snapshot_values,
    list_config_fields,
)


@dataclass
class ScheduleConfigSnapshot:
    sort_strategy: str
    priority_weight: float
    due_weight: float
    ready_weight: float
    holiday_default_efficiency: float
    enforce_ready_default: str
    prefer_primary_skill: str
    dispatch_mode: str
    dispatch_rule: str
    auto_assign_enabled: str
    ortools_enabled: str
    ortools_time_limit_seconds: int
    algo_mode: str
    time_budget_seconds: int
    objective: str
    freeze_window_enabled: str
    freeze_window_days: int
    auto_assign_persist: str = "yes"
    degradation_events: Tuple[Dict[str, Any], ...] = field(default_factory=tuple, repr=False)
    degradation_counters: Dict[str, int] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": float(self.priority_weight),
            "due_weight": float(self.due_weight),
            "ready_weight": float(self.ready_weight),
            "holiday_default_efficiency": float(self.holiday_default_efficiency),
            "enforce_ready_default": self.enforce_ready_default,
            "prefer_primary_skill": self.prefer_primary_skill,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "auto_assign_enabled": self.auto_assign_enabled,
            "auto_assign_persist": self.auto_assign_persist,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": int(self.ortools_time_limit_seconds),
            "algo_mode": self.algo_mode,
            "time_budget_seconds": int(self.time_budget_seconds),
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": int(self.freeze_window_days),
        }


def _read_runtime_cfg_raw_value(cfg: Any, key: str) -> Tuple[bool, Any]:
    if cfg is None:
        return True, None
    if isinstance(cfg, dict):
        if key in cfg:
            return False, cfg.get(key)
        return True, None

    raw_missing = object()
    try:
        value = getattr(cfg, key, raw_missing)
    except ValidationError:
        raise
    except Exception as exc:
        raise _runtime_cfg_read_error(key, exc) from exc
    if value is raw_missing:
        missing, value = _read_runtime_cfg_mapping_like_value(cfg, key, raw_missing)
        if not missing:
            return False, value
        return True, None
    return False, value


def _runtime_cfg_read_error(key: str, exc: Exception) -> ValidationError:
    return ValidationError(f"读取运行期配置字段“{key}”失败：{exc}", field=key)


def _read_runtime_cfg_mapping_like_value(cfg: Any, key: str, raw_missing: object) -> Tuple[bool, Any]:
    getter = getattr(cfg, "get", None)
    if not callable(getter):
        return True, None
    try:
        value = getter(key, raw_missing)
    except TypeError:
        value = _read_runtime_cfg_mapping_like_value_without_default(getter, key, raw_missing)
    except KeyError:
        value = raw_missing
    except ValidationError:
        raise
    except Exception as exc:
        raise _runtime_cfg_read_error(key, exc) from exc
    if value is raw_missing:
        return True, None
    return False, value


def _read_runtime_cfg_mapping_like_value_without_default(getter: Any, key: str, raw_missing: object) -> Any:
    try:
        return getter(key)
    except KeyError:
        return raw_missing
    except ValidationError:
        raise
    except Exception as exc:
        raise _runtime_cfg_read_error(key, exc) from exc


def _coerce_degradation_event(raw: Any) -> Optional[DegradationEvent]:
    if isinstance(raw, DegradationEvent):
        return raw
    if not isinstance(raw, dict):
        return None

    code = str(raw.get("code") or "").strip()
    scope = str(raw.get("scope") or "").strip()
    message = str(raw.get("message") or "").strip()
    if not code or not scope or not message:
        return None

    field_value = raw.get("field")
    field_text = str(field_value).strip() if field_value is not None else ""
    sample_value = raw.get("sample")
    try:
        count = max(1, int(raw.get("count") or 1))
    except Exception:
        count = 1
    return DegradationEvent(
        code=code,
        scope=scope,
        field=field_text or None,
        message=message,
        count=count,
        sample=None if sample_value is None else str(sample_value),
    )


def _seed_snapshot_degradation_collector(snapshot: ScheduleConfigSnapshot) -> DegradationCollector:
    collector = DegradationCollector()
    for raw in getattr(snapshot, "degradation_events", ()) or ():
        event = _coerce_degradation_event(raw)
        if event is not None:
            collector.add(event)
    return collector


def _merge_degradation_counters(*counter_maps: Any) -> Dict[str, int]:
    merged: Dict[str, int] = {}
    for counter_map in counter_maps:
        if not isinstance(counter_map, dict):
            continue
        for key, raw_value in counter_map.items():
            text = str(key or "").strip()
            if not text:
                continue
            try:
                count = int(raw_value)
            except Exception:
                continue
            if count <= 0:
                continue
            merged[text] = max(int(merged.get(text) or 0), count)
    return merged


def _validate_present_runtime_cfg_fields(
    cfg: Any,
    *,
    source: str,
) -> None:
    default_map = default_snapshot_values()
    for spec in list_config_fields():
        missing, raw = _read_runtime_cfg_raw_value(cfg, spec.key)
        if missing:
            continue
        coerce_config_field(
            spec.key,
            raw,
            strict_mode=True,
            source=source,
            collector=DegradationCollector(),
            missing=False,
            fallback=default_map[spec.key],
            missing_policy=MISSING_POLICY_ERROR,
        )


def _build_schedule_config_snapshot_from_runtime_cfg(
    cfg: Any,
    *,
    strict_mode: bool,
    source: str,
) -> ScheduleConfigSnapshot:
    if bool(strict_mode):
        # Strict mode should surface invalid explicit inputs before unrelated
        # missing defaults on raw dict/plain-object configs.
        _validate_present_runtime_cfg_fields(
            cfg,
            source=source,
        )
    collector = (
        _seed_snapshot_degradation_collector(cfg)
        if isinstance(cfg, ScheduleConfigSnapshot)
        else DegradationCollector()
    )
    default_map = default_snapshot_values()
    values: Dict[str, Any] = {}

    for spec in list_config_fields():
        missing, raw = _read_runtime_cfg_raw_value(cfg, spec.key)
        values[spec.key] = coerce_config_field(
            spec.key,
            raw,
            strict_mode=bool(strict_mode),
            source=source,
            collector=collector,
            missing=missing,
            fallback=default_map[spec.key],
            missing_policy=(MISSING_POLICY_ERROR if bool(strict_mode) else MISSING_POLICY_FALLBACK_WITH_DEGRADATION),
        )

    return ScheduleConfigSnapshot(
        sort_strategy=str(values["sort_strategy"]),
        priority_weight=float(values["priority_weight"]),
        due_weight=float(values["due_weight"]),
        ready_weight=float(values["ready_weight"]),
        holiday_default_efficiency=float(values["holiday_default_efficiency"]),
        enforce_ready_default=str(values["enforce_ready_default"]),
        prefer_primary_skill=str(values["prefer_primary_skill"]),
        dispatch_mode=str(values["dispatch_mode"]),
        dispatch_rule=str(values["dispatch_rule"]),
        auto_assign_enabled=str(values["auto_assign_enabled"]),
        auto_assign_persist=str(values["auto_assign_persist"]),
        ortools_enabled=str(values["ortools_enabled"]),
        ortools_time_limit_seconds=int(values["ortools_time_limit_seconds"]),
        algo_mode=str(values["algo_mode"]),
        time_budget_seconds=int(values["time_budget_seconds"]),
        objective=str(values["objective"]),
        freeze_window_enabled=str(values["freeze_window_enabled"]),
        freeze_window_days=int(values["freeze_window_days"]),
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=_merge_degradation_counters(
            getattr(cfg, "degradation_counters", None),
            collector.to_counters(),
        ),
    )


def coerce_runtime_config_field(
    cfg: Any,
    key: str,
    *,
    strict_mode: bool,
    source: str,
    collector: Optional[DegradationCollector] = None,
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> Any:
    default_map = default_snapshot_values()
    missing, raw = _read_runtime_cfg_raw_value(cfg, key)
    active_collector = collector if collector is not None else DegradationCollector()
    return coerce_config_field(
        key,
        raw,
        strict_mode=bool(strict_mode),
        source=source,
        collector=active_collector,
        missing=missing,
        fallback=default_map[key],
        missing_policy=missing_policy,
    )


def ensure_schedule_config_snapshot(
    cfg: Any,
    *,
    strict_mode: bool = False,
    source: str = "scheduler.runtime_config",
) -> ScheduleConfigSnapshot:
    return _build_schedule_config_snapshot_from_runtime_cfg(
        cfg,
        strict_mode=bool(strict_mode),
        source=source,
    )


def build_schedule_config_snapshot(
    repo,
    *,
    defaults: Optional[Dict[str, Any]] = None,
    strict_mode: bool = False,
) -> ScheduleConfigSnapshot:
    collector = DegradationCollector()
    raw_missing = object()
    default_map = default_snapshot_values()
    if isinstance(defaults, dict):
        default_map.update(defaults)

    def _raise_repo_get_contract_error(key: str, record: Any) -> None:
        raise TypeError(
            f"repo.get({key}) 返回值必须为包含 config_value 的 dict，或具备 config_value 属性的记录对象"
            f"（实际={type(record).__name__}）。"
        )

    def _read_repo_raw_value(key: str) -> Tuple[bool, Any]:
        repo_get = getattr(repo, "get", None)
        if callable(repo_get):
            record = repo_get(key)
            if record is None:
                return True, None
            if isinstance(record, dict):
                if "config_value" in record:
                    return False, record.get("config_value")
                _raise_repo_get_contract_error(key, record)
            config_value = getattr(record, "config_value", raw_missing)
            if config_value is not raw_missing:
                return False, config_value
            _raise_repo_get_contract_error(key, record)

        raw = repo.get_value(key, default=raw_missing)
        if raw is raw_missing:
            return True, None
        return False, raw

    if bool(strict_mode):
        for spec in list_config_fields():
            missing, raw = _read_repo_raw_value(spec.key)
            if missing:
                continue
            coerce_config_field(
                spec.key,
                raw,
                strict_mode=True,
                source="scheduler.config_snapshot",
                collector=DegradationCollector(),
                missing=False,
                fallback=default_map[spec.key],
                missing_policy=MISSING_POLICY_ERROR,
            )

    values: Dict[str, Any] = {}
    for spec in list_config_fields():
        missing, raw = _read_repo_raw_value(spec.key)
        values[spec.key] = coerce_config_field(
            spec.key,
            raw,
            strict_mode=bool(strict_mode),
            source="scheduler.config_snapshot",
            collector=collector,
            missing=missing,
            fallback=default_map[spec.key],
            missing_policy=(MISSING_POLICY_ERROR if bool(strict_mode) else MISSING_POLICY_FALLBACK_WITH_DEGRADATION),
        )

    return ScheduleConfigSnapshot(
        sort_strategy=str(values["sort_strategy"]),
        priority_weight=float(values["priority_weight"]),
        due_weight=float(values["due_weight"]),
        ready_weight=float(values["ready_weight"]),
        holiday_default_efficiency=float(values["holiday_default_efficiency"]),
        enforce_ready_default=str(values["enforce_ready_default"]),
        prefer_primary_skill=str(values["prefer_primary_skill"]),
        dispatch_mode=str(values["dispatch_mode"]),
        dispatch_rule=str(values["dispatch_rule"]),
        auto_assign_enabled=str(values["auto_assign_enabled"]),
        auto_assign_persist=str(values["auto_assign_persist"]),
        ortools_enabled=str(values["ortools_enabled"]),
        ortools_time_limit_seconds=int(values["ortools_time_limit_seconds"]),
        algo_mode=str(values["algo_mode"]),
        time_budget_seconds=int(values["time_budget_seconds"]),
        objective=str(values["objective"]),
        freeze_window_enabled=str(values["freeze_window_enabled"]),
        freeze_window_days=int(values["freeze_window_days"]),
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=collector.to_counters(),
    )
