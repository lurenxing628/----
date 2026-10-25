from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
    plan_role_order_sql,
)

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

_SCHEDULE_PLAN_ROWS_SQL = """
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

_CANDIDATE_PLAN_ROWS_SQL = """
SELECT
    id,
    op_id,
    machine_id,
    operator_id,
    start_time,
    end_time,
    lock_status,
    version
FROM ScheduleCandidateRows
WHERE version = ? AND candidate_id = ?
"""

SCENARIO_PLAN_ROWS_SQL = """
SELECT
    r.id,
    r.op_id,
    r.machine_id,
    r.operator_id,
    r.start_time,
    r.end_time,
    r.lock_status,
    s.base_version AS version
FROM ScheduleAdjustmentScenarioRow r
JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id
WHERE s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'
"""

def _require_candidate_id(candidate_id: Optional[int]) -> int:
    if candidate_id is None:
        raise ValueError("candidate_id is required for candidate_rows plan")
    return candidate_id


def _require_scenario_id(scenario_id: Optional[str]) -> str:
    text = (scenario_id or "").strip()
    if not text:
        raise ValueError("scenario_id is required for adjustment_scenario_rows plan")
    return text


class SchedulePlanQueryRepository(BaseRepository):
    """按 adopted / 候选代表方案读取同一形状的排产明细。"""

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
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        if source_table == SOURCE_SCHEDULE:
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
        if source_table == SOURCE_CANDIDATE_ROWS:
            return self.fetchone(
                """
                SELECT id AS source_row_id, lock_status
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (int(version), _require_candidate_id(candidate_id)),
            )
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            scenario_key = _require_scenario_id(scenario_id)
            return self.fetchone(
                """
                SELECT r.id AS source_row_id, r.lock_status
                FROM ScheduleAdjustmentScenarioRow r
                JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id
                WHERE s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'
                ORDER BY r.id ASC
                LIMIT 1
                """,
                (version, scenario_key),
            )
        return None

    def list_plan_role_options(self, version: int) -> List[Dict[str, Any]]:
        return self.fetchall(
            f"""
            SELECT
                s.role AS role,
                s.source_table AS source_table,
                s.candidate_id AS selection_candidate_id,
                c.id AS resolved_candidate_id,
                c.id AS candidate_id,
                c.candidate_key AS candidate_key,
                c.candidate_label AS candidate_label,
                c.candidate_kind AS candidate_kind,
                c.status AS candidate_status,
                c.detail_saved AS detail_saved
            FROM ScheduleCandidateSelection s
            LEFT JOIN ScheduleCandidate c
              ON c.id = s.candidate_id
             AND c.version = s.version
            WHERE s.version = ?
            ORDER BY {plan_role_order_sql("s.role")}
            """,
            (version,),
        )

    def has_candidate_rows(self, *, version: int, candidate_id: int) -> bool:
        return (
            self.fetchone(
                """
                SELECT 1
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                LIMIT 1
                """,
                (version, candidate_id),
            )
            is not None
        )

    def get_scenario_context(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT
                scenario_id,
                source_draft_id,
                base_version,
                base_plan_role,
                base_source_table,
                base_candidate_id,
                base_candidate_key,
                scenario_name,
                status,
                validation_status,
                issue_count,
                issues_json,
                row_count
            FROM ScheduleAdjustmentScenario
            WHERE scenario_id = ?
            """,
            (scenario_id,),
        )

    def has_scenario_rows(self, *, scenario_id: str) -> bool:
        return (
            self.fetchone(
                """
                SELECT 1
                FROM ScheduleAdjustmentScenarioRow
                WHERE scenario_id = ?
                LIMIT 1
                """,
                (scenario_id,),
            )
            is not None
        )

    def _plan_rows_sql(
        self,
        *,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str],
    ) -> Tuple[str, List[Any]]:
        if source_table == SOURCE_SCHEDULE:
            return _SCHEDULE_PLAN_ROWS_SQL, []
        if source_table == SOURCE_CANDIDATE_ROWS:
            return _CANDIDATE_PLAN_ROWS_SQL, [_require_candidate_id(candidate_id)]
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            return SCENARIO_PLAN_ROWS_SQL, [_require_scenario_id(scenario_id)]
        raise ValueError(f"未知的排产方案数据来源：{source_table}")

    def get_plan_time_span(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
    ) -> Optional[ScheduleTimeSpanRow]:
        if source_table == SOURCE_SCHEDULE:
            summary = self.fetchvalue(
                f"""
                SELECT {interval_summary_sql()} AS interval_summary
                FROM Schedule
                WHERE version = ?
                """,
                (version,),
            )
        elif source_table == SOURCE_CANDIDATE_ROWS:
            summary = self.fetchvalue(
                f"""
                SELECT {interval_summary_sql()} AS interval_summary
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                """,
                (version, _require_candidate_id(candidate_id)),
            )
        elif source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            scenario_key = _require_scenario_id(scenario_id)
            summary = self.fetchvalue(
                f"""
                SELECT {interval_summary_sql("r")} AS interval_summary
                FROM ScheduleAdjustmentScenarioRow r
                JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id
                WHERE s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'
                """,
                (version, scenario_key),
            )
        else:
            raise ValueError(f"未知的排产方案数据来源：{source_table}")
        # 无 GROUP BY 的聚合查询恒返回一行；空方案的汇总值由 decode_interval_summary 解释为没有时间段。
        start_time, end_time, _invalid = decode_interval_summary(summary)
        if not start_time or not end_time:
            return None
        return {"version": int(version), "start_time": str(start_time), "end_time": str(end_time)}

    def list_detail_rows_between(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        plan_sql, extra_params = self._plan_rows_sql(
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )
        parsed_start_time = require_dt_for_sql(start_time, "计划明细查询时间写法不对，无法读取排程明细")
        parsed_end_time = require_dt_for_sql(end_time, "计划明细查询时间写法不对，无法读取排程明细")
        params: List[Any] = [int(version)] + extra_params + [parsed_end_time, parsed_start_time]
        where_clauses = [DETAIL_OVERLAP_OR_BAD_TIME_SQL]
        sql = build_schedule_detail_sql(
            where_clauses=where_clauses,
            plan_rows_cte_sql=plan_sql,
        )
        return cast(List[ScheduleDetailRow], self.fetchall(sql, tuple(params)))

    def list_overdue_base_rows(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        allow_points: bool = False,
    ) -> List[Dict[str, Any]]:
        plan_sql, extra_params = self._plan_rows_sql(
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )
        sql = f"""
            WITH plan_rows AS (
                {plan_sql.strip()}
            )
            SELECT
              b.batch_id AS batch_id,
              b.part_no AS part_no,
              b.part_name AS part_name,
              b.quantity AS quantity,
              CAST(b.due_date AS TEXT) AS due_date,
              {interval_summary_sql("s", allow_points=allow_points)} AS interval_summary,
              COUNT(s.id) AS schedule_row_count
            FROM Batches b
            LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
            LEFT JOIN plan_rows s ON s.op_id = bo.id
            WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
            GROUP BY b.batch_id
            ORDER BY b.due_date ASC, b.batch_id ASC
        """
        params: List[Any] = [int(version)] + extra_params
        rows = self.fetchall(sql, tuple(params))
        for row in rows:
            _first, row["finish_time"], row["invalid_time_count"] = decode_interval_summary(row.pop("interval_summary"))
        return rows
