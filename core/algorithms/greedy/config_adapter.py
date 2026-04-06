from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

_CRITICAL_SCHEDULE_KEYS = {"sort_strategy", "dispatch_mode", "dispatch_rule", "auto_assign_enabled"}


@dataclass(frozen=True)
class CriticalConfigReadResult:
    value: Any
    missing: bool = False
    error: Optional[Exception] = None


_MISSING = object()


def cfg_get(config: Any, key: str, default: Any = None) -> Any:
    """
    统一读取配置值，兼容 dict/dataclass/getter 三种形态。
    """
    if config is None:
        return default
    if isinstance(config, dict):
        return config.get(key, default)
    try:
        if hasattr(config, key):
            v = getattr(config, key)
            return default if v is None else v
    except Exception:
        pass
    try:
        getter = getattr(config, "get", None)
        if callable(getter):
            return getter(key, default)
    except Exception:
        pass
    return default


def read_schedule_config_value(config: Any, key: str, default: Any = None) -> CriticalConfigReadResult:
    if config is None:
        return CriticalConfigReadResult(default, missing=True)

    if isinstance(config, dict):
        if key not in config:
            return CriticalConfigReadResult(default, missing=True)
        try:
            value = config[key]
        except Exception as exc:
            return CriticalConfigReadResult(default, error=exc)
        return CriticalConfigReadResult(value)

    try:
        value = getattr(config, key)
    except AttributeError:
        value = _MISSING
    except Exception as exc:
        return CriticalConfigReadResult(default, error=exc)
    else:
        return CriticalConfigReadResult(value)

    try:
        getter = getattr(config, "get", None)
    except Exception as exc:
        return CriticalConfigReadResult(default, error=exc)
    if not callable(getter):
        return CriticalConfigReadResult(default, missing=True)

    try:
        value = getter(key, _MISSING)
    except TypeError:
        try:
            value = getter(key)
        except Exception as exc:
            return CriticalConfigReadResult(default, error=exc)
    except Exception as exc:
        return CriticalConfigReadResult(default, error=exc)

    return CriticalConfigReadResult(default, missing=True) if value is _MISSING else CriticalConfigReadResult(value)


def read_critical_schedule_config(config: Any, key: str, default: Any = None) -> CriticalConfigReadResult:
    if key not in _CRITICAL_SCHEDULE_KEYS:
        raise KeyError(f"unsupported critical schedule key: {key}")

    return read_schedule_config_value(config, key, default)
