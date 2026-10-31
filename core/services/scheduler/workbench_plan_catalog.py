"""Private, SELECT-only plan catalog entry builders; never serialize this module directly to HTML/API.

_role_entry(query, history) builds one PlanCatalogEntry for the
workbench catalog (core/services/workbench/plan/queries.py). The caller owns
the connection, the read snapshot and the paging. resolve_existing_plan admits
detail times through query.repo.get_plan_time_span, which raises ValueError for
invalid detail times or unproven zero-duration work. Capacity rejections propagate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.schedule_plan_role import ADOPTED_PLAN_LABEL, ROLE_ADOPTED
from core.models.scheduler_history_parser import ResultSummaryParseResult
from core.models.workbench_command import WorkbenchCommandRejected
from core.services.common.plan_identity import normalized_result_status
from core.services.common.plan_query import SchedulePlanQueryService

Completeness = Literal["complete", "partial", "invalid", "unknown"]


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


def _history_state(
    history: Dict[str, Any],
    summary_parse: ResultSummaryParseResult,
) -> Tuple[Completeness, Tuple[PlanCatalogIssue, ...]]:
    if summary_parse.parse_failed:
        return "invalid", (PlanCatalogIssue("summary_invalid", summary_parse.reason),)
    if summary_parse.payload is None:
        return "unknown", (PlanCatalogIssue("summary_missing", "排产摘要缺失，无法确认方案身份。"),)
    status = normalized_result_status(history["result_status"])
    statuses: Dict[Optional[str], Completeness] = {"success": "complete", "partial": "partial", "failed": "invalid"}
    state = statuses.get(status, "unknown")
    if summary_parse.payload.get("is_simulation"):
        state = "unknown"
    return state, ()


def _role_entry(query: SchedulePlanQueryService, history: Dict[str, Any]) -> PlanCatalogEntry:
    version = int(history["version"])
    completeness, issues = _history_state(history, query.parse_history_summary(history))
    identity = None
    resolution = None
    try:
        resolution = query.resolve_existing_plan(version)
        identity = resolution.plan_identity
    except (ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, WorkbenchCommandRejected) and exc.status == 413:
            raise
        issues += (PlanCatalogIssue("plan_unavailable", str(exc)),)
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
