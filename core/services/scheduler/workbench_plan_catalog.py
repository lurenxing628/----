"""Private, SELECT-only plan catalog entry builders; never serialize this module directly to HTML/API."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.schedule_plan_role import ADOPTED_PLAN_LABEL, ROLE_ADOPTED
from core.services.common.plan_query import SchedulePlanQueryService

Completeness = Literal["complete", "invalid"]


@dataclass(frozen=True)
class PlanCatalogLocator:
    version: int
    plan_role: str


@dataclass(frozen=True)
class PlanCatalogIssue:
    code: str
    message: str


@dataclass(frozen=True)
class PlanCatalogEntry:
    locator: PlanCatalogLocator
    kind: Literal["official"]
    display_name: str
    completeness: Completeness
    can_view: bool
    blocked_reasons: Tuple[PlanCatalogIssue, ...]
    plan_identity: Optional[PlanIdentity]
    resolution: Optional[SchedulePlanResolution] = None


def plan_catalog_entry(query: SchedulePlanQueryService, history: Dict[str, Any]) -> PlanCatalogEntry:
    version = history["version"]
    completeness: Completeness = "complete"
    issues: Tuple[PlanCatalogIssue, ...] = ()
    identity = None
    resolution = None
    try:
        resolution = query.resolve_existing_plan(version)
        identity = resolution.plan_identity
    except ValueError as exc:
        issues = (PlanCatalogIssue("plan_unavailable", str(exc)),)
        completeness = "invalid"
    return PlanCatalogEntry(
        locator=PlanCatalogLocator(version, ROLE_ADOPTED),
        kind="official",
        display_name=ADOPTED_PLAN_LABEL,
        completeness=completeness,
        can_view=identity is not None and not issues,
        blocked_reasons=issues,
        plan_identity=identity,
        resolution=resolution,
    )
