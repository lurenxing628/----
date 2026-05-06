from __future__ import annotations

from typing import Any, Optional

_TRUE_VALUES = frozenset({"yes", "y", "true", "1", "on"})
_FALSE_VALUES = frozenset({"no", "n", "false", "0", "off"})


def _normalized_form_values(form: Any, name: str) -> list[str]:
    values = form.getlist(name) if hasattr(form, "getlist") else []
    return [str(value or "").strip().lower() for value in values]


def form_yes_no_value(form: Any, name: str, *, default: str = "") -> str:
    values = _normalized_form_values(form, name)
    if any(value in _TRUE_VALUES for value in values):
        return "yes"
    if any(value in _FALSE_VALUES for value in values):
        return "no"
    return str(default or "").strip().lower()


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
