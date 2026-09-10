"""Bounded identity resolution using the same strict and permissive plan query."""

from __future__ import annotations

from dataclasses import replace
from typing import Optional

from core.models.schedule_plan_resolution import SchedulePlanResolution
from data.repositories.workbench_plan_catalog_repo import WorkbenchPlanCatalogRepository

from .plan_identity import build_plan_identity
from .plan_query import SchedulePlanQueryService


class _PagePlanQueryService(SchedulePlanQueryService):
    """Reuse strict resolution, replacing only its all-history identity read."""

    def __init__(self, repo: WorkbenchPlanCatalogRepository, latest: Optional[int]):
        super().__init__(repo.conn, repo=repo)
        self.latest = latest

    def _with_plan_identity(self, resolution: SchedulePlanResolution) -> SchedulePlanResolution:
        history = self.repo.get_history_identity_row(resolution.version) or {}
        source = self.repo.get_first_plan_identity_row(
            version=resolution.version, source_table=resolution.source_table,
            candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id,
        ) or {}
        option = self._option_for_resolution(resolution)
        identity = build_plan_identity(
            version=resolution.version, requested_role=resolution.requested_role,
            effective_role=resolution.selected_role, status=resolution.status,
            source_table=resolution.source_table, source_row_id=source.get("source_row_id"),
            candidate_id=resolution.candidate_id, candidate_key=resolution.candidate_key,
            scenario_id=resolution.scenario_id, scenario_display_name=resolution.scenario_display_name,
            schedule_result_status=history.get("result_status"), result_summary=history.get("result_summary"),
            latest_official_version=self.latest, schedule_lock_status=source.get("lock_status"),
            detail_saved=option.detail_saved if option else None,
        )
        return replace(resolution, plan_identity=identity)
