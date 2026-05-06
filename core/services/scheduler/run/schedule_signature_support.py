from __future__ import annotations

import inspect
from typing import Any, Dict, Optional

_NO_CACHE = object()
_STRICT_MODE_SUPPORT_CACHE: Dict[Any, bool] = {}


def _strict_mode_support_cache_key(schedule_fn: Any) -> Any:
    key = getattr(schedule_fn, "__func__", schedule_fn)
    try:
        hash(key)
    except TypeError:
        return _NO_CACHE
    return key


def clear_strict_mode_support_cache_for_tests() -> None:
    _STRICT_MODE_SUPPORT_CACHE.clear()


def schedule_supports_strict_mode(scheduler: Any) -> Optional[bool]:
    schedule_fn = getattr(scheduler, "schedule", None)
    if not callable(schedule_fn):
        return False

    cache_key = _strict_mode_support_cache_key(schedule_fn)
    if cache_key is not _NO_CACHE and cache_key in _STRICT_MODE_SUPPORT_CACHE:
        return _STRICT_MODE_SUPPORT_CACHE[cache_key]

    try:
        signature = inspect.signature(schedule_fn)
    except (TypeError, ValueError):
        return None

    result = "strict_mode" in signature.parameters
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            result = True
            break

    if cache_key is not _NO_CACHE:
        _STRICT_MODE_SUPPORT_CACHE[cache_key] = bool(result)
    return bool(result)
