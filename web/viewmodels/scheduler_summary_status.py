from __future__ import annotations

from typing import Any


def error_count_blocks_success_inference(value: Any) -> bool:
    if value is None or value == "":
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return False
        normalized = text[1:] if text.startswith("+") else text
        if normalized.isdigit():
            return int(normalized) > 0
        whole, dot, fraction = normalized.partition(".")
        if dot and whole.isdigit() and fraction and set(fraction) == {"0"}:
            return int(whole) > 0
        return True
    return bool(value)
