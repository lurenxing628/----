"""Strict detail-time probe for plan catalog entries, sharing the plan-row SQL of the query repository."""

from __future__ import annotations

from typing import Optional

from .schedule_plan_query_repo import SchedulePlanQueryRepository
from .schedule_time_sql import valid_time_range_sql


class SchedulePlanDetailTimeRepository(SchedulePlanQueryRepository):
    def has_invalid_detail_times(
        self, *, version: int, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str],
    ) -> bool:
        """True when at least one detail row of the plan has an empty, unparsable or non-positive time range."""
        sql, params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id)
        bad = self.fetchone(
            f"SELECT 1 FROM ({sql}) AS p WHERE NOT ({valid_time_range_sql('p')}) LIMIT 1",
            [version] + params,
        )
        return bad is not None
