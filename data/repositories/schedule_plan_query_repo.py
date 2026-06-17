from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from core.models.schedule_plan_role import (
    SOURCE_ADJUSTMENT_SCENARIO_ROWS,
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)
from core.models.schedule_resource_filter import normalize_dispatch_resource_filter

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_resource_sql_filters import append_detail_filters, overdue_resource_filter
from .schedule_rows import ScheduleDetailRow, ScheduleDispatchRow, ScheduleTimeSpanRow
from .schedule_time_sql import DETAIL_OVERLAP_OR_BAD_TIME_SQL, require_dt_for_sql, time_dt, valid_time_range_sql

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

_SCENARIO_PLAN_ROWS_SQL = """
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

def _require_candidate_id(source_table: str, candidate_id: Optional[int]) -> Optional[int]:
    if source_table == SOURCE_CANDIDATE_ROWS and candidate_id is None:
        raise ValueError("candidate_id is required for candidate_rows plan")
    return candidate_id


def _require_scenario_id(source_table: str, scenario_id: Optional[str]) -> str:
    text = str(scenario_id or "").strip()
    if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS and not text:
        raise ValueError("scenario_id is required for adjustment_scenario_rows plan")
    return text


class SchedulePlanQueryRepository(BaseRepository):
    """按 adopted / 候选代表方案读取同一形状的排产明细。"""

    def list_history_identity_rows(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
            SELECT
                h.version,
                h.result_status,
                h.result_summary,
                (
                    SELECT COUNT(1)
                    FROM Schedule s
                    WHERE s.version = h.version
                ) AS schedule_row_count
            FROM ScheduleHistory h
            WHERE h.id = (
                SELECT h2.id
                FROM ScheduleHistory h2
                WHERE h2.version = h.version
                ORDER BY h2.schedule_time DESC, h2.id DESC
                LIMIT 1
            )
            ORDER BY h.version DESC
            """
        )

    def get_history_identity_row(self, version: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            """
            SELECT
                h.version,
                h.result_status,
                h.result_summary,
                (
                    SELECT COUNT(1)
                    FROM Schedule s
                    WHERE s.version = h.version
                ) AS schedule_row_count
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
            _require_candidate_id(source_table, candidate_id)
            return self.fetchone(
                """
                SELECT id AS source_row_id, lock_status
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                ORDER BY id ASC
                LIMIT 1
                """,
                (int(version), int(candidate_id or 0)),
            )
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            scenario_key = _require_scenario_id(source_table, scenario_id)
            return self.fetchone(
                """
                SELECT r.id AS source_row_id, r.lock_status
                FROM ScheduleAdjustmentScenarioRow r
                JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id
                WHERE s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'
                ORDER BY r.id ASC
                LIMIT 1
                """,
                (int(version), scenario_key),
            )
        return None

    def list_plan_role_options(self, version: int) -> List[Dict[str, Any]]:
        return self.fetchall(
            """
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
            ORDER BY
                CASE s.role
                    WHEN 'adopted' THEN 1
                    WHEN 'baseline_best' THEN 2
                    WHEN 'critical_best' THEN 3
                    ELSE 99
                END
            """,
            (int(version),),
        )

    def has_candidate_rows(self, *, version: int, candidate_id: int) -> bool:
        row = self.fetchone(
            """
            SELECT 1
            FROM ScheduleCandidateRows
            WHERE version = ? AND candidate_id = ?
            LIMIT 1
            """,
            (int(version), int(candidate_id)),
        )
        return row is not None

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
                row_count
            FROM ScheduleAdjustmentScenario
            WHERE scenario_id = ?
            """,
            (str(scenario_id),),
        )

    def has_scenario_rows(self, *, scenario_id: str) -> bool:
        row = self.fetchone(
            """
            SELECT 1
            FROM ScheduleAdjustmentScenarioRow
            WHERE scenario_id = ?
            LIMIT 1
            """,
            (str(scenario_id),),
        )
        return row is not None

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
            _require_candidate_id(source_table, candidate_id)
            return _CANDIDATE_PLAN_ROWS_SQL, [int(candidate_id or 0)]
        if source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            return _SCENARIO_PLAN_ROWS_SQL, [_require_scenario_id(source_table, scenario_id)]
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
            row = self.fetchone(
                f"""
                SELECT MIN({time_dt(None, "start_time")}) AS min_start_time,
                       MAX({time_dt(None, "end_time")}) AS max_end_time
                FROM Schedule
                WHERE version = ?
                  AND {valid_time_range_sql(None)}
                """,
                (int(version),),
            )
        elif source_table == SOURCE_CANDIDATE_ROWS:
            _require_candidate_id(source_table, candidate_id)
            row = self.fetchone(
                f"""
                SELECT MIN({time_dt(None, "start_time")}) AS min_start_time,
                       MAX({time_dt(None, "end_time")}) AS max_end_time
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                  AND {valid_time_range_sql(None)}
                """,
                (int(version), int(candidate_id or 0)),
            )
        elif source_table == SOURCE_ADJUSTMENT_SCENARIO_ROWS:
            scenario_key = _require_scenario_id(source_table, scenario_id)
            row = self.fetchone(
                f"""
                SELECT MIN({time_dt("r", "start_time")}) AS min_start_time,
                       MAX({time_dt("r", "end_time")}) AS max_end_time
                FROM ScheduleAdjustmentScenarioRow r
                JOIN ScheduleAdjustmentScenario s ON s.scenario_id = r.scenario_id
                WHERE s.base_version = ? AND r.scenario_id = ? AND s.status = 'active'
                  AND {valid_time_range_sql("r")}
                """,
                (int(version), scenario_key),
            )
        else:
            raise ValueError(f"未知的排产方案数据来源：{source_table}")
        if not row:
            return None
        start_time = row.get("min_start_time")
        end_time = row.get("max_end_time")
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
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
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
        append_detail_filters(
            where_clauses,
            params,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
        sql = build_schedule_detail_sql(
            where_clauses=where_clauses,
            plan_rows_cte_sql=plan_sql,
        )
        return cast(List[ScheduleDetailRow], self.fetchall(sql, tuple(params)))

    def list_detail_rows_all(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[ScheduleDetailRow]:
        plan_sql, extra_params = self._plan_rows_sql(
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )
        params: List[Any] = [int(version)] + extra_params
        where_clauses = ["1 = 1"]
        append_detail_filters(
            where_clauses,
            params,
            batch_id=batch_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
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
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        batch_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        plan_sql, extra_params = self._plan_rows_sql(
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )
        resource_scope = overdue_resource_filter(resource_type, resource_id)
        batch_id_text = str(batch_id or "").strip()
        resource_filter_sql = ""
        resource_params: List[Any] = []
        if resource_scope.has_filter:
            resource_column = resource_scope.column_name
            resource_filter_sql = f"""
              AND EXISTS (
                SELECT 1
                FROM BatchOperations bo2
                JOIN plan_rows sr ON sr.op_id = bo2.id
                WHERE bo2.batch_id = b.batch_id
                  AND TRIM(COALESCE(sr.{resource_column}, '')) = ?
              )
            """
            resource_params.append(resource_scope.resource_id)
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
              MAX(CASE WHEN {valid_time_range_sql("s")} THEN {time_dt("s", "end_time")} ELSE NULL END) AS finish_time,
              COUNT(s.id) AS schedule_row_count,
              COALESCE(
                SUM(CASE WHEN s.id IS NOT NULL AND NOT ({valid_time_range_sql("s")}) THEN 1 ELSE 0 END),
                0
              ) AS invalid_time_count
            FROM Batches b
            LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
            LEFT JOIN plan_rows s ON s.op_id = bo.id
            WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
              AND (? = '' OR TRIM(CAST(b.batch_id AS TEXT)) = ?)
            {resource_filter_sql}
            GROUP BY b.batch_id
            ORDER BY b.due_date ASC, b.batch_id ASC
        """
        params: List[Any] = [int(version)] + extra_params + [batch_id_text, batch_id_text] + resource_params
        return self.fetchall(sql, tuple(params))

    def list_dispatch_rows(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        scenario_id: Optional[str] = None,
        start_time: str,
        end_time: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        schedule_id: Optional[int] = None,
        op_id: Optional[int] = None,
    ) -> List[ScheduleDispatchRow]:
        plan_sql, extra_params = self._plan_rows_sql(
            source_table=source_table,
            candidate_id=candidate_id,
            scenario_id=scenario_id,
        )
        # R05 步3：派工谓词收敛到唯一收口点 normalize_dispatch_resource_filter（含空 id=全量、team 双 join）。
        resource_filter = normalize_dispatch_resource_filter(scope_type, scope_id)
        where_clauses = [DETAIL_OVERLAP_OR_BAD_TIME_SQL]
        parsed_start_time = require_dt_for_sql(start_time, "派工查询时间写法不对，无法读取派工明细")
        parsed_end_time = require_dt_for_sql(end_time, "派工查询时间写法不对，无法读取派工明细")
        params: List[Any] = [int(version)] + extra_params + [parsed_end_time, parsed_start_time]
        if resource_filter.sql_fragment:
            where_clauses.append(resource_filter.sql_fragment)
            params.extend(resource_filter.params)
        batch_id_text = str(batch_id or "").strip()
        if batch_id_text:
            where_clauses.append("TRIM(CAST(bo.batch_id AS TEXT)) = ?")
            params.append(batch_id_text)
        if schedule_id is not None:
            where_clauses.append("s.id = ?")
            params.append(int(schedule_id))
        if op_id is not None:
            where_clauses.append("s.op_id = ?")
            params.append(int(op_id))
        sql = build_schedule_detail_sql(
            where_clauses=tuple(where_clauses),
            # 此 detail SQL 的列面恒带 team 上下文，include_team_context 保持无条件 True，
            # 不随 resource_filter.include_team_context 收窄（收窄会 no such column: o.team_id）。
            include_team_context=True,
            plan_rows_cte_sql=plan_sql,
        )
        return cast(List[ScheduleDispatchRow], self.fetchall(sql, tuple(params)))
