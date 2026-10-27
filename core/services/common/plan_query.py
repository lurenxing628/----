from __future__ import annotations

import sqlite3
from dataclasses import replace
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    SOURCE_SCHEDULE,
    VALID_PLAN_ROLES,
    _normalize_role,
)
from core.models.scheduler_history_parser import ResultSummaryParseResult, parse_result_summary_payload
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
        self.repo: Any = repo if repo is not None else SchedulePlanQueryRepository(conn, logger=logger)
        self._parsed_summaries: Dict[Tuple[Any, Any], ResultSummaryParseResult] = {}

    def parse_history_summary(self, history_row: Mapping[str, Any]) -> ResultSummaryParseResult:
        raw_summary = history_row.get("result_summary")
        key = (history_row.get("version"), raw_summary)
        cached = self._parsed_summaries.get(key)
        if cached is None:
            cached = parse_result_summary_payload(raw_summary)
            self._parsed_summaries[key] = cached
        return cached

    def _latest_official_version(self) -> Optional[int]:
        return self.repo.latest_version()

    def _with_plan_identity(self, resolution: SchedulePlanResolution) -> SchedulePlanResolution:
        history_row = self.repo.get_history_identity_row(int(resolution.version)) or {}
        source_row = self.repo.get_first_plan_identity_row(
            version=int(resolution.version),
            source_table=resolution.source_table,
        ) or {}
        identity = build_plan_identity(
            version=int(resolution.version),
            source_row_id=source_row.get("source_row_id"),
            schedule_result_status=history_row.get("result_status"),
            result_summary=history_row.get("result_summary"),
            latest_official_version=self._latest_official_version(),
            schedule_lock_status=source_row.get("lock_status"),
            summary_parse=self.parse_history_summary(history_row),
        )
        return replace(resolution, plan_identity=identity)

    def resolve_plan(self, version: int, role: Optional[str] = None) -> SchedulePlanResolution:
        requested_role = _normalize_role(role)
        if requested_role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{requested_role}")

        return self._with_plan_identity(SchedulePlanResolution(
            version=int(version),
            requested_role=requested_role,
            selected_role=ROLE_ADOPTED,
            source_table=SOURCE_SCHEDULE,
            status="resolved_adopted",
            message="",
        ))

    def resolve_existing_plan(self, version: int, role: str = ROLE_ADOPTED) -> SchedulePlanResolution:
        if role not in VALID_PLAN_ROLES:
            raise ValueError(f"未知的排产方案角色：{role}")

        if self.repo.get_plan_time_span(
            version=int(version),
            source_table=SOURCE_SCHEDULE,
        ) is None:
            raise ValueError("所选方案没有可查看的明细。")
        return self.resolve_plan(version, role)

    def list_plan_detail_rows_between_for_resolution(
        self,
        *,
        version: int,
        source_table: str = SOURCE_SCHEDULE,
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        return self.repo.list_detail_rows_between(
            version=int(version),
            source_table=source_table,
            start_time=start_time,
            end_time=end_time,
        )

    def list_plan_overdue_base_rows_for_resolution(
        self,
        *,
        version: int,
        source_table: str = SOURCE_SCHEDULE,
    ) -> List[Dict[str, Any]]:
        return self.repo.list_overdue_base_rows(
            version=int(version),
            source_table=source_table,
        )
