from __future__ import annotations

from dataclasses import dataclass

from .schedule_plan_identity import PlanIdentity


@dataclass(frozen=True)
class SchedulePlanResolution:
    version: int
    plan_identity: PlanIdentity


__all__ = ["SchedulePlanResolution"]
