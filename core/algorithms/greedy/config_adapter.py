from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from core.models.schedule_config_runtime import ensure_schedule_config_snapshot


@dataclass(frozen=True)
class CriticalConfigReadResult:
    value: Any
    missing: bool = False
    error: Optional[Exception] = None


def read_schedule_config_value(config: Any, key: str) -> CriticalConfigReadResult:
    snapshot = ensure_schedule_config_snapshot(config)
    if not hasattr(snapshot, key):
        return CriticalConfigReadResult(None, missing=True)
    try:
        return CriticalConfigReadResult(getattr(snapshot, key))
    except Exception as exc:
        return CriticalConfigReadResult(None, error=exc)


def read_critical_schedule_config(config: Any, key: str) -> CriticalConfigReadResult:
    return read_schedule_config_value(config, key)
