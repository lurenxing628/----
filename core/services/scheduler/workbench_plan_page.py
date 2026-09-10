"""Bounded private plan selector pages; no API, UI, permanent refs or writes.

build_history_plan_page(conn, *, page_size=20, before_version=None, logger=None)
  -> HistoryPlanPage(page_size, versions, entries, has_more, next_before_version).
The unit is a DISTINCT history version, not a role: one version returns adopted
plus its stored representative roles (up to three entries under schema rules).
Order is version DESC, then the existing role order. before_version is an
exclusive positive SQLite integer boundary; bool, float and numeric strings are
rejected. The latest identity always uses the actual latest history version,
including partial/failed, regardless of the selected page.

build_scenario_plan_page(conn, *, page_size=20, after_scenario_id=None, logger=None)
  -> ScenarioPlanPage(page_size, scenario_ids, entries, has_more, next_after_scenario_id).
The unit is a saved scenario, in scenario_id BINARY ASC order. The boundary is
exclusive and may refer to a missing key; it is a seek position, not a lookup or
public reference. Published/expired/discarded entries stay unavailable, without
automatic navigation or a fallback to the first page. Only selected active
scenarios and their exact base plans need detail reads.

Both shapes are frozen dataclasses with tuple contents. Empty/exhausted pages
have empty tuples, has_more=False and next_* = None. Maximum page_size is 50.
No total/page number: counting all history or deep OFFSET would defeat seeking.
SQL reads at most page_size+1 keys/headers; only selected items are validated.
No call to build_plan_catalog, full-history scan, or process/global cache.

The caller supplies sqlite3.Row and owns snapshot/transaction lifetime. Each
call creates a fresh repository cache. Cost depends on selected versions' head
records and D_page detail rows, not on all stored detail rows: O(P) SQL queries,
O(P + selected summary bytes) Python memory, and O(D_page) time validation (up
to three role aliases). Indexed seeks still have B-tree costs, and many duplicate
history records for one selected version must be read/sorted to find its head.
There is no fixed latency bound for an individually huge plan. Never claim that
pagination limits per-plan row count or constitutes a scheduling-validity audit.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from dataclasses import replace as replace
from typing import Optional, Tuple

from core.models.schedule_adjustment import ScheduleAdjustmentScenario
from core.models.schedule_plan_resolution import SchedulePlanResolution as SchedulePlanResolution
from core.models.schedule_plan_role import ROLE_ADOPTED
from core.services.common.bounded_plan_query import _PagePlanQueryService as _PagePlanQueryService
from core.services.common.plan_identity import build_plan_identity as build_plan_identity
from core.services.common.plan_query import SchedulePlanQueryService as SchedulePlanQueryService
from data.repositories.workbench_plan_catalog_repo import (
    DEFAULT_PLAN_PAGE_SIZE,
    MAX_PLAN_PAGE_SIZE,
    WorkbenchPlanCatalogRepository,
    validate_after_scenario_id,
    validate_before_version,
    validate_page_size,
)

from .workbench_plan_catalog import PlanCatalogEntry, _role_entry, _scenario_entry


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


def build_history_plan_page(
    conn: sqlite3.Connection, *, page_size: int = DEFAULT_PLAN_PAGE_SIZE,
    before_version: Optional[int] = None, logger=None,
) -> HistoryPlanPage:
    """Read one bounded group of history versions and their actual roles."""
    validate_page_size(page_size)
    validate_before_version(before_version)
    repo = WorkbenchPlanCatalogRepository(conn, logger=logger)
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
    repo = WorkbenchPlanCatalogRepository(conn, logger=logger)
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
