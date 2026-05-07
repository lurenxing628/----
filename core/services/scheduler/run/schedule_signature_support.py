from __future__ import annotations

import inspect
from typing import Any, Dict, Iterable, Optional, Tuple

from core.infrastructure.errors import ValidationError

_NO_CACHE = object()
_STRICT_MODE_SUPPORT_CACHE: Dict[Any, bool] = {}
_KEYWORD_SUPPORT_CACHE: Dict[Tuple[Any, str], bool] = {}


def _strict_mode_support_cache_key(schedule_fn: Any) -> Any:
    key = getattr(schedule_fn, "__func__", schedule_fn)
    try:
        hash(key)
    except TypeError:
        return _NO_CACHE
    return key


def clear_strict_mode_support_cache_for_tests() -> None:
    _STRICT_MODE_SUPPORT_CACHE.clear()
    _KEYWORD_SUPPORT_CACHE.clear()


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


def schedule_supports_keyword(scheduler: Any, keyword: str) -> Optional[bool]:
    schedule_fn = getattr(scheduler, "schedule", None)
    if not callable(schedule_fn):
        return False

    cache_key = _strict_mode_support_cache_key(schedule_fn)
    cache_tuple = (cache_key, str(keyword))
    if cache_key is not _NO_CACHE and cache_tuple in _KEYWORD_SUPPORT_CACHE:
        return _KEYWORD_SUPPORT_CACHE[cache_tuple]

    try:
        signature = inspect.signature(schedule_fn)
    except (TypeError, ValueError):
        return None

    result = str(keyword) in signature.parameters
    for parameter in signature.parameters.values():
        if parameter.kind == inspect.Parameter.VAR_KEYWORD:
            result = True
            break

    if cache_key is not _NO_CACHE:
        _KEYWORD_SUPPORT_CACHE[cache_tuple] = bool(result)
    return bool(result)


def is_unexpected_keyword_type_error(exc: TypeError, keyword: str) -> bool:
    message = str(exc or "")
    return str(keyword) in message and "unexpected keyword argument" in message


def is_unexpected_strict_mode_type_error(exc: TypeError) -> bool:
    return is_unexpected_keyword_type_error(exc, "strict_mode")


def _unsupported_schedule_keyword_message(keyword: str) -> str:
    return f"当前调度器不支持 {keyword}，不能执行启用齐套检查的排产。"


def raise_unsupported_schedule_keyword(keyword: str) -> None:
    raise ValidationError(_unsupported_schedule_keyword_message(keyword), field=str(keyword))


def _without_disabled_readiness_keyword_or_raise(kwargs: Dict[str, Any], exc: TypeError) -> Optional[Dict[str, Any]]:
    if not is_unexpected_keyword_type_error(exc, "readiness_gate_enabled") or "readiness_gate_enabled" not in kwargs:
        return None
    if bool(kwargs.get("readiness_gate_enabled")):
        raise_unsupported_schedule_keyword("readiness_gate_enabled")
    out = dict(kwargs)
    out.pop("readiness_gate_enabled", None)
    return out


def _schedule_without_strict_mode_with_keyword_fallback(scheduler: Any, kwargs: Dict[str, Any]) -> Any:
    try:
        return scheduler.schedule(**kwargs)
    except TypeError as exc:
        retry_kwargs = _without_disabled_readiness_keyword_or_raise(kwargs, exc)
        if retry_kwargs is None:
            raise
    return scheduler.schedule(**retry_kwargs)


def strip_unsupported_schedule_keywords(
    scheduler: Any,
    kwargs: Dict[str, Any],
    keywords: Iterable[str],
    *,
    required_truthy_keywords: Iterable[str] = (),
) -> Dict[str, Any]:
    out = dict(kwargs or {})
    required_truthy = {str(keyword) for keyword in required_truthy_keywords}
    for keyword in keywords:
        keyword = str(keyword)
        if keyword not in out:
            continue
        if schedule_supports_keyword(scheduler, keyword) is False:
            if keyword in required_truthy and bool(out.get(keyword)):
                raise_unsupported_schedule_keyword(keyword)
            out.pop(keyword, None)
    return out


def schedule_with_optional_strict_mode(scheduler: Any, *, strict_mode: bool = False, **kwargs: Any) -> Any:
    kwargs = strip_unsupported_schedule_keywords(
        scheduler,
        kwargs,
        ("readiness_gate_enabled",),
        required_truthy_keywords=("readiness_gate_enabled",),
    )
    supports_strict_mode = schedule_supports_strict_mode(scheduler)
    if supports_strict_mode is True:
        return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))
    if supports_strict_mode is False:
        return scheduler.schedule(**kwargs)

    try:
        return scheduler.schedule(**kwargs, strict_mode=bool(strict_mode))
    except TypeError as exc:
        retry_kwargs = _without_disabled_readiness_keyword_or_raise(kwargs, exc)
        if retry_kwargs is not None:
            return schedule_with_optional_strict_mode(scheduler, strict_mode=bool(strict_mode), **retry_kwargs)
        if not is_unexpected_strict_mode_type_error(exc):
            raise
    return _schedule_without_strict_mode_with_keyword_fallback(scheduler, kwargs)
