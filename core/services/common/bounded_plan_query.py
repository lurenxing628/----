"""Bounded identity resolution using the same strict and permissive plan query."""

from __future__ import annotations

from typing import Optional

from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .plan_query import SchedulePlanQueryService


class _PagePlanQueryService(SchedulePlanQueryService):
    """Reuse strict resolution, replacing only its all-history identity read."""

    def __init__(self, repo: WorkbenchPlanCatalogRepository, latest: Optional[int]):
        super().__init__(repo.conn, repo=repo)
        self.latest = latest

    def _latest_official_version(self) -> Optional[int]:
        return self.latest
