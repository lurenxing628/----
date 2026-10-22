from __future__ import annotations

from typing import Any


def safe_log(logger: Any, level: str, message: str) -> None:
    if logger is None:
        return
    method = getattr(logger, str(level or "").strip(), None)
    if not callable(method):
        return
    try:
        method(message)
    except Exception:
        return


def safe_warning(logger: Any, message: str) -> None:
    safe_log(logger, "warning", message)


def safe_info(logger: Any, message: str) -> None:
    safe_log(logger, "info", message)
