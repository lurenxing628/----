from __future__ import annotations

from typing import Any, Optional, Sequence, Tuple

_YES = "yes"
_NO = "no"
_YES_NO_TRUE_WIDE = ("y", _YES, "true", "1", "on")
_YES_NO_FALSE_WIDE = ("n", _NO, "false", "0", "off", "")


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _normalize_default_yes_no(value: Any) -> str:
    text = _text(value).lower()
    if text in _YES_NO_TRUE_WIDE:
        return _YES
    if text in _YES_NO_FALSE_WIDE:
        return _NO
    return _NO


def _merge_aliases(values: Optional[Sequence[str]]) -> Tuple[str, ...]:
    out = []
    for item in list(values or ()):
        text = _text(item)
        if text:
            out.append(text)
    return tuple(out)


def normalize_yes_no_wide(
    value: Any,
    *,
    default: str = _NO,
    unknown_policy: str = "no",
    true_aliases: Optional[Sequence[str]] = None,
    false_aliases: Optional[Sequence[str]] = None,
) -> str:
    default_norm = _normalize_default_yes_no(default)
    if value is None:
        return default_norm
    text = _text(value)
    lowered = text.lower()
    true_values = {item.lower() for item in _merge_aliases(true_aliases)}
    false_values = {item.lower() for item in _merge_aliases(false_aliases)}
    if text == "":
        return _NO
    if text == "是" or lowered in _YES_NO_TRUE_WIDE or lowered in true_values:
        return _YES
    if text == "否" or lowered in _YES_NO_FALSE_WIDE or lowered in false_values:
        return _NO

    policy = str(unknown_policy or "no").strip().lower()
    if policy == "default":
        return default_norm
    if policy == "passthrough":
        return text
    if policy == "raise":
        raise ValueError(text)
    return _NO
