from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ConfigPageWritePlan:
    updates: List[Any] = field(default_factory=list)
    hidden_repaired_fields: List[str] = field(default_factory=list)
    blocked_hidden_repairs: List[str] = field(default_factory=list)
    notices: List[Dict[str, Any]] = field(default_factory=list)
    active_preset_after: Optional[str] = None
    active_preset_reason_after: Optional[str] = None


__all__ = ["ConfigPageWritePlan"]
