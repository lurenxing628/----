from __future__ import annotations

from typing import Any, Dict, List, Optional, cast

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_rows import ScheduleDetailRow, ScheduleTimeSpanRow
from .schedule_time_sql import (
    DETAIL_OVERLAP_OR_BAD_TIME_SQL,
    decode_interval_summary,
    interval_summary_sql,
    register_schedule_time_sql_functions,
    require_dt_for_sql,
)

SCHEDULE_PLAN_ROWS_SQL = """
SELECT
    id,
    op_id,
    machine_id,
    operator_id,
    start_time,
    end_time,
    lock_status,
    version
FROM Schedule
WHERE version = ?
"""


class SchedulePlanQueryRepository(BaseRepository):
    """按正式排产版本读取排产明细。"""

    def __init__(self, conn, logger=None):
        super().__init__(conn, logger=logger)
        register_schedule_time_sql_functions(conn)

    def latest_version(self) -> Optional[int]:
        return self.fetchvalue("SELECT MAX(version) FROM ScheduleHistory WHERE version > 0", default=None)

    def get_history_identity_row(self, version: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT
                h.version,
                h.result_status,
                h.result_summary
            FROM ScheduleHistory h
            WHERE h.version = ?
            ORDER BY h.schedule_time DESC, h.id DESC
            LIMIT 1
            """,
            (int(version),),
        )

    def get_first_plan_identity_row(
        self,
        *,
        version: int,
    ) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT id AS source_row_id, lock_status
            FROM Schedule
            WHERE version = ?
            ORDER BY id ASC
            LIMIT 1
            """,
            (int(version),),
        )

    def get_plan_time_span(
        self,
        *,
        version: int,
    ) -> Optional[ScheduleTimeSpanRow]:
        summary = self.fetchvalue(
            f"""
            SELECT {interval_summary_sql()} AS interval_summary
            FROM Schedule
            WHERE version = ?
            """,
            (version,),
        )
        # 无 GROUP BY 的聚合查询恒返回一行；空方案的汇总值由 decode_interval_summary 解释为没有时间段。
        start_time, end_time, _invalid = decode_interval_summary(summary)
        if not start_time or not end_time:
            return None
        return {"version": int(version), "start_time": str(start_time), "end_time": str(end_time)}

    def list_detail_rows_between(
        self,
        *,
        version: int,
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        parsed_start_time = require_dt_for_sql(start_time, "计划明细查询时间写法不对，无法读取排程明细")
        parsed_end_time = require_dt_for_sql(end_time, "计划明细查询时间写法不对，无法读取排程明细")
        params: List[Any] = [int(version), parsed_end_time, parsed_start_time]
        where_clauses = [DETAIL_OVERLAP_OR_BAD_TIME_SQL]
        sql = build_schedule_detail_sql(
            where_clauses=where_clauses,
            plan_rows_cte_sql=SCHEDULE_PLAN_ROWS_SQL,
        )
        return cast(List[ScheduleDetailRow], self.fetchall(sql, tuple(params)))

    def list_overdue_base_rows(
        self,
        *,
        version: int,
    ) -> List[Dict[str, Any]]:
        """零工时点事件（开工即完工）是合法安排，计入完工时间，不算时间无效行。"""
        sql = f"""
            WITH plan_rows AS (
                {SCHEDULE_PLAN_ROWS_SQL.strip()}
            )
            SELECT
              b.batch_id AS batch_id,
              b.part_no AS part_no,
              b.part_name AS part_name,
              b.quantity AS quantity,
              CAST(b.due_date AS TEXT) AS due_date,
              {interval_summary_sql("s", allow_points=True)} AS interval_summary,
              COUNT(s.id) AS schedule_row_count
            FROM Batches b
            LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
            LEFT JOIN plan_rows s ON s.op_id = bo.id
            WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
            GROUP BY b.batch_id
            ORDER BY b.due_date ASC, b.batch_id ASC
        """
        rows = self.fetchall(sql, (int(version),))
        for row in rows:
            _first, row["finish_time"], row["invalid_time_count"] = decode_interval_summary(row.pop("interval_summary"))
        return rows
