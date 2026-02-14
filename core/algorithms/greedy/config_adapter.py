from __future__ import annotations

from typing import Any


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

