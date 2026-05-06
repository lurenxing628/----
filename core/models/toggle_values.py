from __future__ import annotations

from typing import Any

TOGGLE_TRUE_VALUES = frozenset({"yes", "y", "true", "1", "on"})
TOGGLE_FALSE_VALUES = frozenset({"no", "n", "false", "0", "off"})
TOGGLE_SUBMIT_VALUES = TOGGLE_TRUE_VALUES | TOGGLE_FALSE_VALUES


def normalize_toggle_submit_value(value: Any) -> str:
    return "" if value is None else str(value).strip().lower()


__all__ = [
    "TOGGLE_FALSE_VALUES",
    "TOGGLE_SUBMIT_VALUES",
    "TOGGLE_TRUE_VALUES",
    "normalize_toggle_submit_value",
]
