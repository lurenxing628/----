from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)

STATE_AVAILABLE = "available"
STATE_DEGRADED = "degraded"
STATE_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class CapabilityResult:
    name: str
    state: str
    reason: str = ""
    details: Optional[Dict[str, str]] = None

    @property
    def available(self) -> bool:
        return self.state == STATE_AVAILABLE

    @property
    def degraded(self) -> bool:
        return self.state == STATE_DEGRADED

    @property
    def unavailable(self) -> bool:
        return self.state == STATE_UNAVAILABLE


def available(name: str, details: Optional[Dict[str, str]] = None) -> CapabilityResult:
    return CapabilityResult(name=name, state=STATE_AVAILABLE, details=details or {})


def degraded(name: str, reason: str, details: Optional[Dict[str, str]] = None) -> CapabilityResult:
    normalized_reason = _require_reason(reason, state=STATE_DEGRADED)
    normalized_details = details or {}
    logger.warning("启动能力降级：%s reason=%s details=%s", name, normalized_reason, normalized_details)
    return CapabilityResult(name=name, state=STATE_DEGRADED, reason=normalized_reason, details=normalized_details)


def unavailable(name: str, reason: str, details: Optional[Dict[str, str]] = None) -> CapabilityResult:
    normalized_reason = _require_reason(reason, state=STATE_UNAVAILABLE)
    normalized_details = details or {}
    logger.warning("启动能力不可用：%s reason=%s details=%s", name, normalized_reason, normalized_details)
    return CapabilityResult(name=name, state=STATE_UNAVAILABLE, reason=normalized_reason, details=normalized_details)


def _require_reason(reason: str, *, state: str) -> str:
    normalized = str(reason or "").strip()
    if not normalized:
        raise ValueError(f"{state} capability requires reason")
    return normalized
