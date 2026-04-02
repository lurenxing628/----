from __future__ import annotations

from typing import Any, Optional


def safe_log(logger: Any, level: str, message: str, *, exc_info: Optional[bool] = None) -> bool:
    if logger is None:
        return False
    method = getattr(logger, str(level or "").strip(), None)
    if not callable(method):
        return False
    try:
        if exc_info is None:
            method(message)
        else:
            try:
                method(message, exc_info=bool(exc_info))
            except TypeError:
                method(message)
        return True
    except Exception:
        return False


def safe_warning(logger: Any, message: str, *, exc_info: Optional[bool] = None) -> bool:
    return safe_log(logger, "warning", message, exc_info=exc_info)


def safe_info(logger: Any, message: str, *, exc_info: Optional[bool] = None) -> bool:
    return safe_log(logger, "info", message, exc_info=exc_info)
