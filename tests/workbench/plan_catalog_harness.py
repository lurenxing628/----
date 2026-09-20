"""Test-only oracles over the live plan catalog entry builders.

Retired from production on 2026-09-20: the public catalog API
(core/services/workbench/plan/queries.py) pages and binds permanent references
itself and only shares _role_entry / _scenario_entry with these oracles.

build_plan_catalog(conn, logger=None) -> List[PlanCatalogEntry]: the complete
private catalog. Order: history versions descending, adopted then stored
representative roles; then scenarios by base_version descending, created_at
descending, scenario_id. SELECT-only on the caller's connection; missing
tables or DB errors propagate; an initialized empty database returns [].

build_history_plan_page / build_scenario_plan_page: the private bounded pages.
The unit is a DISTINCT history version (adopted plus its stored roles) in
version DESC order with an exclusive before_version seek, or a saved scenario
in scenario_id BINARY ASC order with an exclusive after_scenario_id seek.
Default 20, maximum 50; SQL reads page_size+1 keys and validates only the
selected plans. Published/expired/discarded scenarios stay listed but unavailable.

Both oracles validate detail times with the strict SQL probe the retired
SchedulePlanDetailTimeRepository used; the public API validates through
PointPlanCatalogRepository instead.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import List, Optional, Tuple

from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.common.bounded_plan_query import _PagePlanQueryService
from core.services.common.plan_identity import latest_official_version
from core.services.common.plan_query import SchedulePlanQueryService
from core.services.scheduler.workbench_plan_catalog import PlanCatalogEntry, _role_entry, _scenario_entry
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.schedule_time_sql import valid_time_range_sql
from data.repositories.workbench_plan_catalog_repo import (
    DEFAULT_PLAN_PAGE_SIZE,
    WorkbenchPlanCatalogRepository,
    validate_after_scenario_id,
    validate_before_version,
    validate_page_size,
)

INVALID_DETAIL_TIME_MESSAGE = "方案包含无效时间明细，不能标记为完整可查看。"


def _validate_detail_times(repo: SchedulePlanQueryRepository, resolution: SchedulePlanResolution) -> None:
    """Raise ValueError when any detail row of the plan has an empty, unparsable or non-positive range."""
    sql, params = repo._plan_rows_sql(
        source_table=resolution.source_table, candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id,
    )
    bad = repo.fetchone(
        f"SELECT 1 FROM ({sql}) AS p WHERE NOT ({valid_time_range_sql('p')}) LIMIT 1",
        [resolution.version] + params,
    )
    if bad is not None:
        raise ValueError(INVALID_DETAIL_TIME_MESSAGE)


class CatalogProbeRepository(SchedulePlanQueryRepository):
    def validate_detail_times(self, resolution: SchedulePlanResolution) -> None:
        _validate_detail_times(self, resolution)


class PageProbeRepository(WorkbenchPlanCatalogRepository):
    def validate_detail_times(self, resolution: SchedulePlanResolution) -> None:
        _validate_detail_times(self, resolution)


@dataclass(frozen=True)
class HistoryPlanPage:
    page_size: int
    versions: Tuple[int, ...]
    entries: Tuple[PlanCatalogEntry, ...]
    has_more: bool
    next_before_version: Optional[int]


@dataclass(frozen=True)
class ScenarioPlanPage:
    page_size: int
    scenario_ids: Tuple[str, ...]
    entries: Tuple[PlanCatalogEntry, ...]
    has_more: bool
    next_after_scenario_id: Optional[str]


def build_plan_catalog(conn: sqlite3.Connection, logger=None) -> List[PlanCatalogEntry]:
    """List stored identities without fallback, mutation, or public references."""
    repo = CatalogProbeRepository(conn, logger=logger)
    query = SchedulePlanQueryService(conn, logger=logger, repo=repo)
    histories = repo.list_history_identity_rows()
    latest = latest_official_version(histories)
    entries = []
    for history in histories:
        rows = repo.list_plan_role_options(int(history["version"]))
        adopted = next((row for row in rows if row["role"] == ROLE_ADOPTED), None)
        entries.append(_role_entry(query, history, latest, ROLE_ADOPTED, adopted))
        entries.extend(
            _role_entry(query, history, latest, str(row["role"]), row)
            for row in rows if row["role"] != ROLE_ADOPTED
        )
    by_version = {int(row["version"]): row for row in histories}
    scenarios = repo.fetchall(
        "SELECT * FROM ScheduleAdjustmentScenario ORDER BY base_version DESC, created_at DESC, scenario_id"
    )
    for row in scenarios:
        scenario = ScheduleAdjustmentScenario.from_row(row)
        entries.append(_scenario_entry(query, scenario, by_version.get(scenario.base_version), latest))
    return entries


def build_history_plan_page(
    conn: sqlite3.Connection, *, page_size: int = DEFAULT_PLAN_PAGE_SIZE,
    before_version: Optional[int] = None, logger=None,
) -> HistoryPlanPage:
    """Read one bounded group of history versions and their actual roles."""
    validate_page_size(page_size)
    validate_before_version(before_version)
    repo = PageProbeRepository(conn, logger=logger)
    histories, has_more = repo.history_page(page_size=page_size, before_version=before_version)
    latest = repo.latest_version() if histories else None
    query = _PagePlanQueryService(repo, latest)
    entries = []
    for history in histories:
        rows = repo.list_plan_role_options(int(history["version"]))
        adopted = next((row for row in rows if row["role"] == ROLE_ADOPTED), None)
        entries.append(_role_entry(query, history, latest, ROLE_ADOPTED, adopted))
        entries.extend(
            _role_entry(query, history, latest, str(row["role"]), row)
            for row in rows if row["role"] != ROLE_ADOPTED
        )
    versions = tuple(int(history["version"]) for history in histories)
    return HistoryPlanPage(page_size, versions, tuple(entries), has_more, versions[-1] if has_more else None)


def build_scenario_plan_page(
    conn: sqlite3.Connection, *, page_size: int = DEFAULT_PLAN_PAGE_SIZE,
    after_scenario_id: Optional[str] = None, logger=None,
) -> ScenarioPlanPage:
    """Read one bounded group of scenario headers, including unavailable ones."""
    validate_page_size(page_size)
    validate_after_scenario_id(after_scenario_id)
    repo = PageProbeRepository(conn, logger=logger)
    rows, has_more = repo.scenario_page(page_size=page_size, after_scenario_id=after_scenario_id)
    latest = repo.latest_version() if rows else None
    query = _PagePlanQueryService(repo, latest)
    entries = []
    for row in rows:
        scenario = ScheduleAdjustmentScenario.from_row(row)
        history = repo.get_history_identity_row(scenario.base_version)
        entries.append(_scenario_entry(query, scenario, history, latest))
    ids = tuple(str(row["scenario_id"]) for row in rows)
    return ScenarioPlanPage(page_size, ids, tuple(entries), has_more, ids[-1] if has_more else None)
