"""Private, SELECT-only plan catalog; never serialize this module directly to HTML/API.

build_plan_catalog(conn, logger=None) -> List[PlanCatalogEntry]. The caller owns
the connection (sqlite3.Row factory) and any read-snapshot transaction. No schema,
configuration, app, token registry, or command service is initialized here.

Shape is frozen dataclasses, not a public JSON contract:
* locator: PlanCatalogLocator(version, plan_role, scenario_id); internal only.
* kind: official/candidate/scenario describes storage provenance, NOT permission.
* display_name, is_latest_version, schedule_result_status preserve history facts.
* role_option: existing SchedulePlanRoleOption, or None for an unreadable binding
  or a scenario. plan_identity: existing PlanIdentity, or None if strict lookup
  failed. Its current-official flags, never kind/latest alone, govern identity.
* completeness: complete/partial/invalid/unknown. Official results use the saved
  history status and strict summary parser. Candidate completion and scenario
  validation do not prove scheduling completeness, so remain unknown here.
* can_view: bool; blocked_reasons: tuple of PlanCatalogIssue(code, message).
  Missing detail, broken bindings, invalid times and summaries stay visible as
  unavailable entries. Candidate/scenario completeness is unknown unless invalid
  data is detected; it never inherits a different plan's completion result.
* scenario_status and published_version: None for non-scenarios. Published,
  discarded and expired scenarios remain listed but cannot preview; a published
  version is an internal navigation hint, never an automatic substitution.

Order: history versions descending, adopted then stored representative roles;
then scenarios by base_version descending, created_at descending, scenario_id.
History deduplication and latest selection use the existing repository/builder:
latest partial/failed never falls back to an older success. Unselected candidate
attempts and editing drafts are not plans in this catalog. Missing tables or DB
errors propagate; an initialized empty database returns []. Per-plan validation
failures are reported without fabricating a healthy identity or hiding entries.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, replace
from typing import Any, Dict, List, Literal, Optional, Tuple

from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution, SchedulePlanRoleOption
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE, plan_role_label
from core.models.scheduler_history_parser import parse_result_summary_payload
from data.repositories.schedule_time_sql import valid_time_range_sql

from .schedule_plan_identity_builder import latest_official_version
from .schedule_plan_query_service import SchedulePlanQueryService

Completeness = Literal["complete", "partial", "invalid", "unknown"]


@dataclass(frozen=True)
class PlanCatalogLocator:
    version: int
    plan_role: str
    scenario_id: Optional[str] = None


@dataclass(frozen=True)
class PlanCatalogIssue:
    code: str
    message: str


@dataclass(frozen=True)
class PlanCatalogEntry:
    locator: PlanCatalogLocator
    kind: Literal["official", "candidate", "scenario"]
    display_name: str
    is_latest_version: bool
    schedule_result_status: Optional[str]
    completeness: Completeness
    can_view: bool
    blocked_reasons: Tuple[PlanCatalogIssue, ...]
    plan_identity: Optional[PlanIdentity]
    role_option: Optional[SchedulePlanRoleOption]
    scenario_status: Optional[str] = None
    published_version: Optional[int] = None


def _history_state(history: Dict[str, Any]) -> Tuple[Completeness, Tuple[PlanCatalogIssue, ...]]:
    parsed = parse_result_summary_payload(history.get("result_summary"))
    if parsed.parse_failed:
        return "invalid", (PlanCatalogIssue("summary_invalid", parsed.reason),)
    if parsed.payload is None:
        return "unknown", (PlanCatalogIssue("summary_missing", "排产摘要缺失，无法确认方案身份。"),)
    status = str(history.get("result_status") or "").strip().lower()
    statuses: Dict[str, Completeness] = {"success": "complete", "partial": "partial", "failed": "invalid"}
    state = statuses.get(status, "unknown")
    if parsed.payload.get("is_simulation"):
        state = "unknown"
    return state, ()


def _check_role_binding(resolution: SchedulePlanResolution, option: SchedulePlanRoleOption) -> None:
    if option.candidate_id is not None and option.candidate_status != "completed":
        raise ValueError("方案角色指向的候选不是已完成状态。")
    if option.source_table == SOURCE_SCHEDULE:
        adopted = next(item for item in resolution.available_roles if item.role == ROLE_ADOPTED)
        if option.candidate_id != adopted.candidate_id:
            raise ValueError("共用正式排程的对比角色没有指向正式采用候选。")


def _check_detail_times(query: SchedulePlanQueryService, resolution: SchedulePlanResolution) -> None:
    validate = getattr(query.repo, "validate_detail_times", None)
    if callable(validate):
        validate(resolution)
        return
    sql, params = query.repo._plan_rows_sql(
        source_table=resolution.source_table, candidate_id=resolution.candidate_id,
        scenario_id=resolution.scenario_id,
    )
    bad = query.repo.fetchone(
        f"SELECT 1 FROM ({sql}) AS p WHERE NOT ({valid_time_range_sql('p')}) LIMIT 1",
        [resolution.version] + params,
    )
    if bad is not None:
        raise ValueError("方案包含无效时间明细，不能标记为完整可查看。")


def _role_entry(
    query: SchedulePlanQueryService, history: Dict[str, Any], latest: Optional[int],
    role: str, raw_option: Optional[Dict[str, Any]],
) -> PlanCatalogEntry:
    version = int(history["version"])
    completeness, issues = _history_state(history)
    option = None
    identity = None
    try:
        if raw_option is not None:
            option = query._role_option_from_row(raw_option)
        resolution = query.resolve_existing_plan(version, role)
        option = next(item for item in resolution.available_roles if item.role == role)
        _check_role_binding(resolution, option)
        _check_detail_times(query, resolution)
        identity = resolution.plan_identity
    except (ValueError, TypeError, OverflowError) as exc:
        issues += (PlanCatalogIssue("plan_unavailable", str(exc)),)
        completeness = "invalid"
    if role != ROLE_ADOPTED and not issues:
        completeness = "unknown"
    return PlanCatalogEntry(
        locator=PlanCatalogLocator(version, role),
        kind="official" if role == ROLE_ADOPTED else "candidate",
        display_name=option.candidate_label if option else plan_role_label(role),
        is_latest_version=version == latest,
        schedule_result_status=history.get("result_status"),
        completeness=completeness,
        can_view=identity is not None and not issues,
        blocked_reasons=issues,
        plan_identity=identity,
        role_option=option,
    )


def _scenario_resolution(query: SchedulePlanQueryService, scenario: ScheduleAdjustmentScenario) -> PlanIdentity:
    base = query.resolve_existing_plan(scenario.base_version, scenario.base_plan_role)
    base_option = next(item for item in base.available_roles if item.role == scenario.base_plan_role)
    _check_role_binding(base, base_option)
    if (scenario.base_source_table, scenario.base_candidate_id, scenario.base_candidate_key) != (
        base.source_table, base.candidate_id, base.candidate_key
    ):
        raise ValueError("模拟方案的基础角色关系与已保存方案不一致。")
    resolution = query.resolve_plan_view(scenario.base_version, scenario.base_plan_role, scenario.scenario_id)
    span = query.get_plan_time_span_for_resolution(
        version=resolution.version, source_table=resolution.source_table,
        candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id,
    )
    if span is None:
        raise ValueError("模拟方案没有可查看的有效时间明细。")
    if resolution.plan_identity is None:
        raise ValueError("模拟方案没有可确认的计划身份。")
    _check_detail_times(query, resolution)
    # Existing scenario resolution has no role detail_saved flag for its own rows.
    return replace(resolution.plan_identity, detail_saved=True)


def _scenario_entry(
    query: SchedulePlanQueryService, scenario: ScheduleAdjustmentScenario,
    history: Optional[Dict[str, Any]], latest: Optional[int],
) -> PlanCatalogEntry:
    issues: Tuple[PlanCatalogIssue, ...] = ()
    identity = None
    completeness: Completeness = "unknown"
    if history is None:
        issues = (PlanCatalogIssue("history_missing", "模拟方案的基础排产历史不存在。"),)
        completeness = "invalid"
    else:
        history_state, issues = _history_state(history)
        if issues and history_state == "invalid":
            completeness = "invalid"
    if scenario.status != "active":
        message = "模拟方案已正式采用，请查看其发布版本。" if scenario.status == "published" else "模拟方案不是可预览状态。"
        issues += (PlanCatalogIssue("scenario_not_active", message),)
    elif history is not None:
        try:
            identity = _scenario_resolution(query, scenario)
        except (ValueError, TypeError, OverflowError) as exc:
            issues += (PlanCatalogIssue("scenario_unavailable", str(exc)),)
            completeness = "invalid"
    return PlanCatalogEntry(
        locator=PlanCatalogLocator(scenario.base_version, scenario.base_plan_role, scenario.scenario_id),
        kind="scenario",
        display_name=scenario.scenario_name or "试调方案（未命名）",
        is_latest_version=scenario.base_version == latest,
        schedule_result_status=history.get("result_status") if history else None,
        completeness=completeness,
        can_view=identity is not None and not issues,
        blocked_reasons=issues,
        plan_identity=identity,
        role_option=None,
        scenario_status=scenario.status,
        published_version=scenario.published_version,
    )


def build_plan_catalog(conn: sqlite3.Connection, logger=None) -> List[PlanCatalogEntry]:
    """List stored identities without fallback, mutation, or public references."""
    query = SchedulePlanQueryService(conn, logger=logger)
    histories = query.repo.list_history_identity_rows()
    latest = latest_official_version(histories)
    entries = []
    for history in histories:
        rows = query.repo.list_plan_role_options(int(history["version"]))
        adopted = next((row for row in rows if row["role"] == ROLE_ADOPTED), None)
        entries.append(_role_entry(query, history, latest, ROLE_ADOPTED, adopted))
        entries.extend(
            _role_entry(query, history, latest, str(row["role"]), row)
            for row in rows if row["role"] != ROLE_ADOPTED
        )
    by_version = {int(row["version"]): row for row in histories}
    scenarios = query.repo.fetchall(
        "SELECT * FROM ScheduleAdjustmentScenario ORDER BY base_version DESC, created_at DESC, scenario_id"
    )
    for row in scenarios:
        scenario = ScheduleAdjustmentScenario.from_row(row)
        entries.append(_scenario_entry(query, scenario, by_version.get(scenario.base_version), latest))
    return entries
