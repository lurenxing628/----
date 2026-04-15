from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Tuple

from core.infrastructure.errors import ValidationError
from core.services.common.degradation import DegradationCollector, degradation_events_to_dicts
from core.services.common.field_parse import parse_field_float, parse_field_int

from ..number_utils import to_yes_no


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
    degradation_events: Tuple[Dict[str, Any], ...] = field(default_factory=tuple, repr=False)
    degradation_counters: Dict[str, int] = field(default_factory=dict, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sort_strategy": self.sort_strategy,
            "priority_weight": self.priority_weight,
            "due_weight": self.due_weight,
            "ready_weight": self.ready_weight,
            "holiday_default_efficiency": float(self.holiday_default_efficiency),
            "enforce_ready_default": self.enforce_ready_default,
            "prefer_primary_skill": self.prefer_primary_skill,
            "dispatch_mode": self.dispatch_mode,
            "dispatch_rule": self.dispatch_rule,
            "auto_assign_enabled": self.auto_assign_enabled,
            "ortools_enabled": self.ortools_enabled,
            "ortools_time_limit_seconds": int(self.ortools_time_limit_seconds),
            "algo_mode": self.algo_mode,
            "time_budget_seconds": int(self.time_budget_seconds),
            "objective": self.objective,
            "freeze_window_enabled": self.freeze_window_enabled,
            "freeze_window_days": int(self.freeze_window_days),
        }


def _normalize_valid_texts(values: Tuple[str, ...]) -> Tuple[str, ...]:
    out = []
    seen = set()
    for item in values or ():
        text = str(item).strip().lower()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return tuple(out)


def _format_choice_allow_text(valid_values: Tuple[str, ...]) -> str:
    return " / ".join(valid_values) if valid_values else "<empty>"


def _record_blank_choice_degradation(
    collector: DegradationCollector,
    *,
    scope: str,
    field: str,
    raw_value: Any,
    fallback: str,
) -> None:
    collector.add(
        code="blank_required",
        scope=scope,
        field=field,
        message=f"字段“{field}”为空，已按兼容读取回退为 {fallback}。",
        sample=repr(raw_value),
    )


def _record_invalid_choice_degradation(
    collector: DegradationCollector,
    *,
    scope: str,
    field: str,
    raw_value: Any,
    fallback: str,
    valid_values: Tuple[str, ...],
) -> None:
    collector.add(
        code="invalid_choice",
        scope=scope,
        field=field,
        message=(
            f"字段“{field}”取值不合法（当前值：{raw_value!r}，允许值：{_format_choice_allow_text(valid_values)}），"
            f"已按兼容读取回退为 {fallback}。"
        ),
        sample=repr(raw_value),
    )


def _choice_with_degradation(
    raw_value: Any,
    *,
    field: str,
    fallback: str,
    valid_values: Tuple[str, ...],
    strict_mode: bool,
    collector: DegradationCollector,
    scope: str,
    missing: bool = False,
) -> str:
    normalized_valid = _normalize_valid_texts(valid_values)
    fallback_text = str(fallback or "").strip().lower()
    if normalized_valid and fallback_text not in normalized_valid:
        fallback_text = normalized_valid[0]
    if missing:
        return fallback_text

    text = "" if raw_value is None else str(raw_value).strip().lower()
    if strict_mode and text == "":
        raise ValidationError(f"“{field}”不能为空", field=field)
    if text == "":
        _record_blank_choice_degradation(collector, scope=scope, field=field, raw_value=raw_value, fallback=fallback_text)
        return fallback_text
    if normalized_valid and text not in normalized_valid:
        if strict_mode:
            raise ValidationError(
                f"“{field}”取值不合法：{raw_value!r}（允许值：{_format_choice_allow_text(normalized_valid)}）",
                field=field,
            )
        _record_invalid_choice_degradation(
            collector,
            scope=scope,
            field=field,
            raw_value=raw_value,
            fallback=fallback_text,
            valid_values=normalized_valid,
        )
        return fallback_text
    return text if normalized_valid else fallback_text


def _yes_no_with_degradation(
    raw_value: Any,
    *,
    field: str,
    fallback: str,
    strict_mode: bool,
    collector: DegradationCollector,
    scope: str,
    missing: bool = False,
) -> str:
    normalized_default = to_yes_no(fallback, default=fallback)
    if missing:
        return normalized_default

    text = "" if raw_value is None else str(raw_value).strip().lower()
    true_vals = {"yes", "y", "true", "1", "on"}
    false_vals = {"no", "n", "false", "0", "off"}
    if strict_mode and text == "":
        raise ValidationError(f"“{field}”不能为空", field=field)
    if text == "":
        _record_blank_choice_degradation(collector, scope=scope, field=field, raw_value=raw_value, fallback=normalized_default)
        return normalized_default
    if text not in true_vals and text not in false_vals:
        if strict_mode:
            raise ValidationError(f"“{field}”取值不合法：{raw_value!r}（允许值：yes / no）", field=field)
        _record_invalid_choice_degradation(
            collector,
            scope=scope,
            field=field,
            raw_value=raw_value,
            fallback=normalized_default,
            valid_values=("yes", "no"),
        )
        return normalized_default
    return to_yes_no(raw_value, default=normalized_default)


def build_schedule_config_snapshot(
    repo,
    *,
    defaults: Dict[str, Any],
    valid_strategies: Tuple[str, ...],
    valid_dispatch_modes: Tuple[str, ...],
    valid_dispatch_rules: Tuple[str, ...],
    valid_algo_modes: Tuple[str, ...],
    valid_objectives: Tuple[str, ...],
    strict_mode: bool = False,
) -> ScheduleConfigSnapshot:
    collector = DegradationCollector()
    raw_missing = object()

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

    def _read_repo_text_value(key: str, default_text: str) -> str:
        missing, raw = _read_repo_raw_value(key)
        if missing:
            return str(default_text)
        return "" if raw is None else str(raw)

    def _choice(key: str, default: Any, valid: Tuple[str, ...], *, strict: bool = False) -> str:
        missing, raw = _read_repo_raw_value(key)
        return _choice_with_degradation(
            raw,
            field=key,
            fallback=str(default or "").strip().lower(),
            valid_values=valid,
            strict_mode=bool(strict),
            collector=collector,
            scope="scheduler.config_snapshot",
            missing=missing,
        )

    def _yes_no(key: str, default: str, *, strict: bool = False) -> str:
        missing, raw = _read_repo_raw_value(key)
        return _yes_no_with_degradation(
            raw,
            field=key,
            fallback=str(default or "").strip().lower(),
            strict_mode=bool(strict),
            collector=collector,
            scope="scheduler.config_snapshot",
            missing=missing,
        )

    def _get_float(
        key: str,
        default: float,
        *,
        min_value: float | None = None,
        min_inclusive: bool = True,
    ) -> float:
        raw = _read_repo_text_value(key, str(default))
        return parse_field_float(
            raw,
            field=key,
            strict_mode=bool(strict_mode),
            scope="scheduler.config_snapshot",
            fallback=float(default),
            collector=collector,
            min_value=min_value,
            min_inclusive=min_inclusive,
        )

    def _get_int(
        key: str,
        default: int,
        *,
        min_value: int | None = None,
        min_violation_fallback: int | None = None,
    ) -> int:
        raw = _read_repo_text_value(key, str(default))
        return parse_field_int(
            raw,
            field=key,
            strict_mode=bool(strict_mode),
            scope="scheduler.config_snapshot",
            fallback=int(default),
            collector=collector,
            min_value=min_value,
            min_violation_fallback=int(default if min_violation_fallback is None else min_violation_fallback),
        )

    strategy = _choice("sort_strategy", defaults["sort_strategy"], valid_strategies, strict=bool(strict_mode))
    pw = _get_float("priority_weight", float(defaults["priority_weight"]), min_value=0.0)
    dw = _get_float("due_weight", float(defaults["due_weight"]), min_value=0.0)
    rw = _get_float("ready_weight", float(defaults["ready_weight"]), min_value=0.0)
    hde = _get_float(
        "holiday_default_efficiency",
        float(defaults["holiday_default_efficiency"]),
        min_value=0.0,
        min_inclusive=False,
    )

    enforce_ready_default = _yes_no(
        "enforce_ready_default",
        str(defaults.get("enforce_ready_default", "no")),
        strict=bool(strict_mode),
    )
    pref = _yes_no(
        "prefer_primary_skill",
        str(defaults.get("prefer_primary_skill", "no")),
        strict=bool(strict_mode),
    )

    dm = _choice("dispatch_mode", defaults["dispatch_mode"], valid_dispatch_modes, strict=bool(strict_mode))
    dr = _choice("dispatch_rule", defaults["dispatch_rule"], valid_dispatch_rules, strict=bool(strict_mode))

    aa = _yes_no("auto_assign_enabled", str(defaults["auto_assign_enabled"]), strict=bool(strict_mode))
    ort = _yes_no("ortools_enabled", str(defaults["ortools_enabled"]), strict=bool(strict_mode))
    ort_limit = _get_int(
        "ortools_time_limit_seconds",
        int(defaults["ortools_time_limit_seconds"]),
        min_value=1,
        min_violation_fallback=1,
    )

    algo_mode = _choice("algo_mode", defaults["algo_mode"], valid_algo_modes, strict=bool(strict_mode))
    obj = _choice("objective", defaults["objective"], valid_objectives, strict=bool(strict_mode))
    time_budget = _get_int(
        "time_budget_seconds",
        int(defaults["time_budget_seconds"]),
        min_value=1,
        min_violation_fallback=1,
    )

    fw_enabled = _yes_no("freeze_window_enabled", str(defaults["freeze_window_enabled"]), strict=bool(strict_mode))
    fw_days = _get_int(
        "freeze_window_days",
        int(defaults["freeze_window_days"]),
        min_value=0,
        min_violation_fallback=0,
    )

    return ScheduleConfigSnapshot(
        sort_strategy=strategy,
        priority_weight=pw,
        due_weight=dw,
        ready_weight=rw,
        holiday_default_efficiency=float(hde),
        enforce_ready_default=enforce_ready_default,
        prefer_primary_skill=pref,
        dispatch_mode=dm,
        dispatch_rule=dr,
        auto_assign_enabled=aa,
        ortools_enabled=ort,
        ortools_time_limit_seconds=int(ort_limit),
        algo_mode=algo_mode,
        time_budget_seconds=int(time_budget),
        objective=obj,
        freeze_window_enabled=fw_enabled,
        freeze_window_days=int(fw_days),
        degradation_events=tuple(degradation_events_to_dicts(collector.to_list())),
        degradation_counters=collector.to_counters(),
    )
