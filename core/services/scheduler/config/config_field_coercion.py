"""Service labels and legacy omission policy adapt the common field coercion."""

from __future__ import annotations

from typing import Any, Optional

from core.models.schedule_config_runtime_coercion import (
    coerce_config_field as coerce_runtime_value,
)
from core.models.schedule_config_runtime_coercion import (
    float_matches_choice as _float_matches_choice,
)
from core.models.schedule_config_runtime_coercion import (
    normalize_choice_tokens as _normalize_valid_texts,
)
from core.shared.boolean_normalize import to_yes_no
from core.shared.degradation import DegradationCollector

from .config_field_spec import (
    MISSING_POLICY_FALLBACK_WITH_DEGRADATION,
    MISSING_POLICY_INHERIT_LEGACY_OMISSION,
    get_field_spec,
)

_UNSET = object()


def normalize_text_field(key: str, value: Any) -> str:
    spec = get_field_spec(key)
    if spec.field_type == "yes_no":
        return to_yes_no(value, default=str(spec.default))
    return "" if value is None else str(value).strip().lower()


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
    effective_fallback = spec.default if fallback is _UNSET else fallback
    if missing and str(missing_policy).strip().lower() == MISSING_POLICY_INHERIT_LEGACY_OMISSION:
        if spec.field_type == "enum":
            text = str(effective_fallback or "").strip().lower()
            return text if text in spec.choices else spec.choices[0]
        if spec.field_type == "yes_no":
            return to_yes_no(effective_fallback, default=str(effective_fallback))
        return effective_fallback
    return coerce_runtime_value(
        key, value, strict_mode=strict_mode, source=source, collector=collector,
        missing=missing, fallback=effective_fallback, missing_policy=missing_policy,
        field_label=spec.label,
    )


__all__ = ["coerce_config_field", "normalize_text_field"]
