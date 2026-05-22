from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple, cast

from core.models.schedule_plan_role import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_rows import ScheduleDetailRow, ScheduleDispatchRow, ScheduleTimeSpanRow

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


def _require_candidate_id(source_table: str, candidate_id: Optional[int]) -> Optional[int]:
    if source_table == SOURCE_CANDIDATE_ROWS and candidate_id is None:
        raise ValueError("candidate_id is required for candidate_rows plan")
    return candidate_id


class SchedulePlanQueryRepository(BaseRepository):
    """按 adopted / 候选代表方案读取同一形状的排产明细。"""

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

    def _plan_rows_sql(self, *, source_table: str, candidate_id: Optional[int]) -> Tuple[str, List[Any]]:
        if source_table == SOURCE_SCHEDULE:
            return _SCHEDULE_PLAN_ROWS_SQL, []
        if source_table == SOURCE_CANDIDATE_ROWS:
            _require_candidate_id(source_table, candidate_id)
            return _CANDIDATE_PLAN_ROWS_SQL, [int(candidate_id or 0)]
        raise ValueError(f"未知的排产方案数据来源：{source_table}")

    def get_plan_time_span(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
    ) -> Optional[ScheduleTimeSpanRow]:
        if source_table == SOURCE_SCHEDULE:
            row = self.fetchone(
                """
                SELECT MIN(start_time) AS min_start_time, MAX(end_time) AS max_end_time
                FROM Schedule
                WHERE version = ?
                  AND TRIM(CAST(start_time AS TEXT)) <> ''
                  AND TRIM(CAST(end_time AS TEXT)) <> ''
                """,
                (int(version),),
            )
        elif source_table == SOURCE_CANDIDATE_ROWS:
            _require_candidate_id(source_table, candidate_id)
            row = self.fetchone(
                """
                SELECT MIN(start_time) AS min_start_time, MAX(end_time) AS max_end_time
                FROM ScheduleCandidateRows
                WHERE version = ? AND candidate_id = ?
                  AND TRIM(CAST(start_time AS TEXT)) <> ''
                  AND TRIM(CAST(end_time AS TEXT)) <> ''
                """,
                (int(version), int(candidate_id or 0)),
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
        start_time: str,
        end_time: str,
    ) -> List[ScheduleDetailRow]:
        plan_sql, extra_params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id)
        sql = build_schedule_detail_sql(
            where_clauses=("s.start_time < ?", "s.end_time > ?"),
            plan_rows_cte_sql=plan_sql,
        )
        params: List[Any] = [int(version)] + extra_params + [end_time, start_time]
        return cast(List[ScheduleDetailRow], self.fetchall(sql, tuple(params)))

    def list_detail_rows_all(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
    ) -> List[ScheduleDetailRow]:
        plan_sql, extra_params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id)
        sql = build_schedule_detail_sql(
            where_clauses=("1 = 1",),
            plan_rows_cte_sql=plan_sql,
        )
        params: List[Any] = [int(version)] + extra_params
        return cast(List[ScheduleDetailRow], self.fetchall(sql, tuple(params)))

    def list_overdue_base_rows(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
    ) -> List[Dict[str, Any]]:
        plan_sql, extra_params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id)
        sql = f"""
            WITH plan_rows AS (
                {plan_sql.strip()}
            )
            SELECT
              b.batch_id AS batch_id,
              b.part_no AS part_no,
              b.part_name AS part_name,
              b.quantity AS quantity,
              b.due_date AS due_date,
              MAX(s.end_time) AS finish_time
            FROM Batches b
            LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
            LEFT JOIN plan_rows s ON s.op_id = bo.id
            WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
            GROUP BY b.batch_id
            ORDER BY b.due_date ASC, b.batch_id ASC
        """
        params: List[Any] = [int(version)] + extra_params
        return self.fetchall(sql, tuple(params))

    def list_dispatch_rows(
        self,
        *,
        version: int,
        source_table: str,
        candidate_id: Optional[int],
        start_time: str,
        end_time: str,
        scope_type: Optional[str] = None,
        scope_id: Optional[str] = None,
    ) -> List[ScheduleDispatchRow]:
        plan_sql, extra_params = self._plan_rows_sql(source_table=source_table, candidate_id=candidate_id)
        scope_type_text = str(scope_type or "").strip().lower()
        scope_id_text = str(scope_id or "").strip()
        where_clauses = ["s.start_time < ?", "s.end_time > ?"]
        params: List[Any] = [int(version)] + extra_params + [end_time, start_time]
        if scope_type_text == "operator" and scope_id_text:
            where_clauses.append("TRIM(COALESCE(s.operator_id, '')) = ?")
            params.append(scope_id_text)
        elif scope_type_text == "operator":
            where_clauses.append("TRIM(COALESCE(s.operator_id, '')) <> ''")
        elif scope_type_text == "machine" and scope_id_text:
            where_clauses.append("TRIM(COALESCE(s.machine_id, '')) = ?")
            params.append(scope_id_text)
        elif scope_type_text == "machine":
            where_clauses.append("TRIM(COALESCE(s.machine_id, '')) <> ''")
        elif scope_type_text == "team" and scope_id_text:
            where_clauses.append("((o.team_id = ?) OR (m.team_id = ?))")
            params.extend([scope_id_text, scope_id_text])
        sql = build_schedule_detail_sql(
            where_clauses=tuple(where_clauses),
            include_team_context=True,
            plan_rows_cte_sql=plan_sql,
        )
        return cast(List[ScheduleDispatchRow], self.fetchall(sql, tuple(params)))
