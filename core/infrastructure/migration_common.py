"""Shared logging helper owned by the infrastructure parent layer."""

from __future__ import annotations

from core.infrastructure.logging import safe_log


def fallback_log(logger, level: str, message: str) -> None:
    if not logger:
        return
    safe_log(logger, level, str(message))


__all__ = [
    "fallback_log",
]
