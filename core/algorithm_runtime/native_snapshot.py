"""Exact, side-effect-free content certificates for native scheduling inputs."""

import math
from datetime import date, datetime, time
from typing import Any

UNSUPPORTED = object()
_SCALARS = (type(None), bool, int, str, date, datetime, time)


def scalar_snapshot(value) -> Any:
    kind = type(value)
    if kind in _SCALARS:
        if kind in (datetime, time) and value.tzinfo is not None:
            return UNSUPPORTED
        return kind, value
    if kind is float and math.isfinite(value):
        return kind, value
    return UNSUPPORTED


def content_snapshot(value, _depth=0) -> Any:
    scalar = scalar_snapshot(value)
    if scalar is not UNSUPPORTED:
        return scalar
    kind = type(value)
    if kind not in (dict, list, tuple, set, frozenset) or _depth > 12:
        return UNSUPPORTED
    if kind is dict:
        items = [(content_snapshot(key, _depth + 1), content_snapshot(item, _depth + 1)) for key, item in value.items()]
        if any(key is UNSUPPORTED or item is UNSUPPORTED for key, item in items):
            return UNSUPPORTED
        return kind, frozenset(items)
    items = [content_snapshot(item, _depth + 1) for item in value]
    if any(item is UNSUPPORTED for item in items):
        return UNSUPPORTED
    return kind, frozenset(items) if kind in (set, frozenset) else tuple(items)
