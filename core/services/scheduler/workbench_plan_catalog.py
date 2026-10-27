"""Private, SELECT-only plan catalog entry builders; never serialize this module directly to HTML/API.

_role_entry(query, history, latest) builds one PlanCatalogEntry for the
workbench catalog (core/services/workbench/plan/queries.py). The caller owns
the connection, the read snapshot and the paging; query.repo must provide
validate_detail_times (PointPlanCatalogRepository in production), which raises
ValueError for invalid detail times or unproven zero-duration work. Capacity
rejections propagate.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Literal, Optional, Tuple

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.schedule_plan_role import ROLE_ADOPTED, plan_role_label
from core.models.scheduler_history_parser import ResultSummaryParseResult
from core.models.workbench_command import WorkbenchCommandRejected
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
    is_latest_version: bool
    schedule_result_status: Optional[str]
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
    status = str(history.get("result_status") or "").strip().lower()
    statuses: Dict[str, Completeness] = {"success": "complete", "partial": "partial", "failed": "invalid"}
    state = statuses.get(status, "unknown")
    if summary_parse.payload.get("is_simulation"):
        state = "unknown"
    return state, ()


def _role_entry(
    query: SchedulePlanQueryService, history: Dict[str, Any], latest: Optional[int],
) -> PlanCatalogEntry:
    version = int(history["version"])
    completeness, issues = _history_state(history, query.parse_history_summary(history))
    identity = None
    resolution = None
    try:
        resolution = query.resolve_existing_plan(version, ROLE_ADOPTED)
        query.repo.validate_detail_times(resolution)
        identity = resolution.plan_identity
    except (ValueError, TypeError, OverflowError) as exc:
        if isinstance(exc, WorkbenchCommandRejected) and exc.status == 413:
            raise
        issues += (PlanCatalogIssue("plan_unavailable", str(exc)),)
        completeness = "invalid"
    return PlanCatalogEntry(
        locator=PlanCatalogLocator(version, ROLE_ADOPTED),
        kind="official",
        display_name=plan_role_label(ROLE_ADOPTED),
        is_latest_version=version == latest,
        schedule_result_status=history.get("result_status"),
        completeness=completeness,
        can_view=identity is not None and not issues,
        blocked_reasons=issues,
        plan_identity=identity,
        resolution=resolution,
    )
