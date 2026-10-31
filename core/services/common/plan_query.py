from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Mapping, Optional

from core.infrastructure.read_evidence import verified_read
from core.models.schedule_plan_identity import PlanIdentity
from core.models.schedule_plan_resolution import SchedulePlanResolution
from core.models.scheduler_history_parser import ResultSummaryParseResult, parse_result_summary_payload
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from data.repositories.schedule_rows import ScheduleDetailRow

from .plan_identity import build_plan_identity


def snapshot_summary_parse(conn: sqlite3.Connection, raw_summary: Any) -> ResultSummaryParseResult:
    """Decode one stored ``result_summary`` text once per read-evidence snapshot.

    The parse depends on the text alone, so every reader of the same text in the
    snapshot shares it; outside a snapshot this is a plain parse.
    """
    return verified_read(conn, ("result_summary_parse", raw_summary),
                         lambda: parse_result_summary_payload(raw_summary))


class SchedulePlanQueryService:
    """统一解析正式排产方案，并按同一字段形状读取明细。"""

    def __init__(
        self,
        conn: sqlite3.Connection,
        logger=None,
        repo: Optional[SchedulePlanQueryRepository] = None,
    ):
        self.conn = conn
        self.repo: Any = repo if repo is not None else SchedulePlanQueryRepository(conn, logger=logger)
        self._parsed_summaries: Dict[Any, ResultSummaryParseResult] = {}

    def parse_history_summary(self, history_row: Mapping[str, Any]) -> ResultSummaryParseResult:
        raw_summary = history_row.get("result_summary")
        cached = self._parsed_summaries.get(raw_summary)
        if cached is None:
            cached = snapshot_summary_parse(self.conn, raw_summary)
            self._parsed_summaries[raw_summary] = cached
        return cached

    def _latest_official_version(self) -> Optional[int]:
        return self.repo.latest_version()

    def _build_plan_identity(self, version: int) -> PlanIdentity:
        history_row = self.repo.get_history_identity_row(version) or {}
        source_row = self.repo.get_first_plan_identity_row(
            version=version,
        ) or {}
        return build_plan_identity(
            version=version,
            source_row_id=source_row.get("source_row_id"),
            schedule_result_status=history_row.get("result_status"),
            latest_official_version=self._latest_official_version(),
            summary_parse=self.parse_history_summary(history_row),
        )

    def _resolve_validated_plan(self, version: int) -> SchedulePlanResolution:
        normalized_version = int(version)
        return SchedulePlanResolution(
            version=normalized_version,
            plan_identity=self._build_plan_identity(normalized_version),
        )

    def resolve_plan(self, version: int) -> SchedulePlanResolution:
        return self._resolve_validated_plan(version)

    def resolve_existing_plan(self, version: int) -> SchedulePlanResolution:
        if self.repo.get_plan_time_span(
            version=int(version),
        ) is None:
            raise ValueError("所选方案没有可查看的明细。")
        return self._resolve_validated_plan(version)

    def list_plan_detail_rows_between_for_resolution(
        self,
        *,
        version: int,
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        return self.repo.list_detail_rows_between(
            version=int(version),
            start_time=start_time,
            end_time=end_time,
        )

    def list_plan_overdue_base_rows_for_resolution(
        self,
        *,
        version: int,
    ) -> List[Dict[str, Any]]:
        return self.repo.list_overdue_base_rows(
            version=int(version),
        )
