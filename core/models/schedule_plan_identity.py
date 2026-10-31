from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PlanIdentity:
    version: Optional[int]
    is_current_executable_official_version: bool
    can_write_feedback: bool


__all__ = ["PlanIdentity"]
