from __future__ import annotations

from typing import Any, Optional, Tuple

from core.infrastructure.errors import ValidationError
from core.shared.degradation import DegradationCollector
from core.shared.field_parse import parse_field_float, parse_field_int

from ..number_utils import to_yes_no
from .config_field_spec import (
    MISSING_POLICY_ERROR,
    MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
    MISSING_POLICY_INHERIT_LEGACY_OMISSION,
    get_field_spec,
)

_UNSET = object()


def normalize_text_field(key: str, value: Any) -> str:
    spec = get_field_spec(key)
    text = "" if value is None else str(value).strip().lower()
    if spec.field_type == "yes_no":
        return to_yes_no(value, default=str(spec.default))
    return text


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


def _handle_missing_value(
    collector: DegradationCollector,
    *,
    field: str,
    fallback: Any,
    scope: str,
    missing_policy: str,
) -> tuple[bool, Any]:
    policy = str(missing_policy or MISSING_POLICY_FALLBACK_WITH_DEGRADATION).strip().lower()
    if policy == MISSING_POLICY_ERROR:
        raise ValidationError(f"缺少“{field}”配置", field=field)
    if policy == MISSING_POLICY_INHERIT_LEGACY_OMISSION:
        return True, fallback
    collector.add(
        code="missing_required",
        scope=scope,
        field=field,
        message=f"字段“{field}”缺失，已按兼容读取回退为 {fallback}。",
        sample=None,
    )
    return True, fallback


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
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> str:
    normalized_valid = _normalize_valid_texts(valid_values)
    fallback_text = str(fallback or "").strip().lower()
    if normalized_valid and fallback_text not in normalized_valid:
        fallback_text = normalized_valid[0]
    if missing:
        _, handled = _handle_missing_value(
            collector,
            field=field,
            fallback=fallback_text,
            scope=scope,
            missing_policy=missing_policy,
        )
        return str(handled).strip().lower()

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
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> str:
    normalized_default = to_yes_no(fallback, default=fallback)
    if missing:
        _, handled = _handle_missing_value(
            collector,
            field=field,
            fallback=normalized_default,
            scope=scope,
            missing_policy=missing_policy,
        )
        return to_yes_no(handled, default=normalized_default)

    text = "" if raw_value is None else str(raw_value).strip().lower()
    true_vals = {"yes", "y", "true", "1", "on"}
    false_vals = {"no", "n", "false", "0", "off"}
    if strict_mode and text == "":
        raise ValidationError(f"“{field}”不能为空", field=field)
    if text == "":
        _record_blank_choice_degradation(
            collector,
            scope=scope,
            field=field,
            raw_value=raw_value,
            fallback=normalized_default,
        )
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


def coerce_config_field(
    key: str,
    value: Any,
    *,
    strict_mode: bool,
    source: str,
    collector: Optional[DegradationCollector] = None,
    missing: bool = False,
    fallback: Any = _UNSET,
    missing_policy: str = MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
) -> Any:
    spec = get_field_spec(key)
    active_collector = collector if collector is not None else DegradationCollector()
    effective_fallback = spec.default if fallback is _UNSET else fallback

    if spec.field_type == "enum":
        return _choice_with_degradation(
            value,
            field=spec.key,
            fallback=str(effective_fallback or "").strip().lower(),
            valid_values=tuple(spec.choices),
            strict_mode=bool(strict_mode),
            collector=active_collector,
            scope=source,
            missing=bool(missing),
            missing_policy=missing_policy,
        )
    if spec.field_type == "yes_no":
        return _yes_no_with_degradation(
            value,
            field=spec.key,
            fallback=str(effective_fallback or "").strip().lower(),
            strict_mode=bool(strict_mode),
            collector=active_collector,
            scope=source,
            missing=bool(missing),
            missing_policy=missing_policy,
        )
    if missing:
        _, handled = _handle_missing_value(
            active_collector,
            field=spec.key,
            fallback=effective_fallback,
            scope=source,
            missing_policy=missing_policy,
        )
        return handled
    if spec.field_type == "float":
        return float(
            parse_field_float(
                value,
                field=spec.key,
                strict_mode=bool(strict_mode),
                scope=source,
                fallback=float(effective_fallback),
                collector=active_collector,
                min_value=spec.min_value,
                min_inclusive=bool(spec.min_inclusive),
            )
        )
    if spec.field_type == "int":
        min_violation_fallback = int(effective_fallback)
        if spec.min_value is not None:
            min_violation_fallback = int(spec.min_value)
        return int(
            parse_field_int(
                value,
                field=spec.key,
                strict_mode=bool(strict_mode),
                scope=source,
                fallback=int(effective_fallback),
                collector=active_collector,
                min_value=(None if spec.min_value is None else int(spec.min_value)),
                min_violation_fallback=min_violation_fallback,
            )
        )
    raise TypeError(f"不支持的配置字段类型：{spec.field_type!r}")


__all__ = ["coerce_config_field", "normalize_text_field"]
