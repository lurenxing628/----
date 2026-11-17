from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional

from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.schedule_rows import ScheduleDetailRow

from .plan_identity import build_plan_identity


class SchedulePlanQueryService:
    """统一解析正式排产方案，并按同一字段形状读取明细。"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        logger=None,
        repo: Optional[SchedulePlanQueryRepository] = None,
    ):
        if repo is None:
            repo = SchedulePlanQueryRepository(conn, logger=logger)
        self.repo: Any = repo

    def _latest_official_version(self) -> Optional[int]:
        return self.repo.latest_version()

    def _build_plan_identity(self, version: int, *, source_row: Optional[Dict[str, Any]]) -> PlanIdentity:
        history_row = self.repo.get_history_row(version)
        return build_plan_identity(
            version=version,
            source_row_id=source_row["source_row_id"] if source_row is not None else None,
            schedule_result_status=history_row["result_status"] if history_row is not None else None,
            latest_official_version=self._latest_official_version(),
        )

    def resolve_plan(self, version: int) -> SchedulePlanResolution:
        normalized_version = int(version)
        source_row = self.repo.get_first_plan_identity_row(version=normalized_version)
        return SchedulePlanResolution(
            version=normalized_version,
            plan_identity=self._build_plan_identity(normalized_version, source_row=source_row),
        )

    def resolve_existing_plan(self, version: int) -> SchedulePlanResolution:
        normalized_version = int(version)
        source_row = self.repo.get_first_plan_identity_row(version=normalized_version)
        if source_row is None or self.repo.get_plan_time_span(version=normalized_version) is None:
            raise ValueError("所选方案没有可查看的明细。")
        return SchedulePlanResolution(
            version=normalized_version,
            plan_identity=self._build_plan_identity(normalized_version, source_row=source_row),
        )

    def list_plan_detail_rows_between_for_resolution(
        self,
        *,
        version: int,
        start: datetime,
        end: datetime,
    ) -> List[ScheduleDetailRow]:
        return self.repo.list_detail_rows_between(
            version=int(version),
            start=start,
            end=end,
        )

    def list_plan_overdue_base_rows_for_resolution(
        self,
        *,
        version: int,
    ) -> List[Dict[str, Any]]:
        return self.repo.list_overdue_base_rows(
            version=int(version),
        )
