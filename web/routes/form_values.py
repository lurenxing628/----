from __future__ import annotations

from typing import Any, Optional

from core.infrastructure.errors import ValidationError
from core.models.toggle_values import TOGGLE_FALSE_VALUES, TOGGLE_TRUE_VALUES, normalize_toggle_submit_value


def _normalized_form_values(form: Any, name: str) -> list[str]:
    if hasattr(form, "getlist"):
        values = form.getlist(name)
    else:
        try:
            contains_field = name in form
        except TypeError:
            contains_field = False
        if not contains_field or not hasattr(form, "get"):
            values = []
        else:
            raw_value = form.get(name)
            values = list(raw_value) if isinstance(raw_value, (list, tuple)) else [raw_value]
    return [normalize_toggle_submit_value(value) for value in values]


def form_yes_no_value(form: Any, name: str, *, default: str = "") -> str:
    values = _normalized_form_values(form, name)
    if not values:
        return _normalize_yes_no_default(default, name=name)
    invalid_values = [
        value for value in values if value not in TOGGLE_TRUE_VALUES and value not in TOGGLE_FALSE_VALUES
    ]
    if invalid_values:
        raise ValidationError(f"{name} 取值不合法，只能是 yes/no。", field=name)
    if any(value in TOGGLE_TRUE_VALUES for value in values):
        return "yes"
    return "no"


def _normalize_yes_no_default(default: str, *, name: str) -> str:
    value = str(default or "").strip().lower()
    if not value:
        return ""
    if value in TOGGLE_TRUE_VALUES:
        return "yes"
    if value in TOGGLE_FALSE_VALUES:
        return "no"
    raise ValidationError(f"{name} 默认值不合法，只能是 yes/no。", field=name)


def form_toggle_bool(form: Any, name: str, *, default: bool = False) -> bool:
    value = form_yes_no_value(form, name, default="yes" if default else "no")
    return value == "yes"


def form_optional_toggle_bool(form: Any, name: str) -> Optional[bool]:
    if name not in form:
        return None
    return form_toggle_bool(form, name, default=False)


__all__ = [
    "form_optional_toggle_bool",
    "form_toggle_bool",
    "form_yes_no_value",
]
