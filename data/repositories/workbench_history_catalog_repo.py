"""SQL queries and transactional persistence for WorkbenchHistoryEntries."""

import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .base_repo import BaseRepository

_RUN_ORDINALS_CTE = """
WITH run_ordinals AS (
    SELECT entry_ref,
           ROW_NUMBER() OVER (
               ORDER BY occurred_us IS NULL ASC, occurred_us ASC, run_ref ASC
           ) AS run_no
    FROM WorkbenchHistoryEntries
    WHERE source_kind = 'run'
)
"""

_OUTER_COLUMNS = """
    p.entry_ref,
    p.timeline,
    p.source_kind,
    p.effective_state,
    p.occurred_at,
    p.occurred_day,
    p.occurred_us,
    p.time_basis,
    CASE WHEN p.source_kind = 'run'
         THEN '第' || CAST(ro.run_no AS TEXT) || '次运行'
         ELSE p.static_label
    END AS display_label,
    p.run_ref,
    p.candidate_ref,
    p.scenario_ref,
    p.draft_ref,
    p.plan_ref,
    p.plan_version,
    p.receipt_ref,
    p.request_key,
    p.baseline_plan_ref,
    p.baseline_version,
    p.selected_candidate_ref,
    p.selection_json,
    p.times_json,
    p.evidence_gaps_json,
    p.objective_json,
    p.static_condition_digest,
    p.default_7d_calendar_digest,
    p.live_job_started_at,
    rj.normalized_input_json AS run_normalized_input_json,
    h.version AS existing_history_version
"""


def _where_clause(
    timeline: str,
    state: str,
    date_from: Any,
    date_to: Any,
) -> Tuple[str, List[Any]]:
    clauses = ["e.timeline = ?"]
    params: List[Any] = [timeline]
    if state != "all":
        if state == "queued":
            clauses.append("e.state = 'queued' AND COALESCE(j.state, e.state) = 'queued'")
        elif state == "running":
            clauses.append("e.state IN ('queued', 'running') AND COALESCE(j.state, e.state) = 'running'")
        else:
            clauses.append("e.state = ?")
            params.append(state)
    if date_from is not None:
        clauses.append("e.occurred_day IS NOT NULL AND e.occurred_day >= ? AND e.occurred_day <= ?")
        params.extend([date_from, date_to])
    return " AND ".join(clauses), params


def _order_clause(order: str) -> str:
    if order == "asc":
        return "e.occurred_us IS NULL ASC, e.occurred_us ASC, e.entry_ref ASC"
    return (
        "e.occurred_us IS NULL ASC, e.occurred_us DESC, "
        "IIF(e.occurred_us IS NULL, e.entry_ref, NULL) ASC, e.entry_ref DESC"
    )


class WorkbenchHistoryCatalogRepository(BaseRepository):
    def directory_summary(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """SELECT e.timeline,
                      COALESCE(j.state, e.state) AS effective_state,
                      COUNT(*) AS cnt,
                      COALESCE(MAX(e.rowid), 0) AS max_rowid,
                      COUNT(e.receipt_ref) AS receipt_cnt,
                      COALESCE(MAX(e.occurred_us), -1) AS max_occurred_us
               FROM WorkbenchHistoryEntries e
               LEFT JOIN WorkbenchRunJobs j
                 ON e.source_kind = 'run' AND e.state = 'queued' AND j.run_ref = e.run_ref
               GROUP BY e.timeline, effective_state
               ORDER BY e.timeline, effective_state"""
        )

    def active_runs_state(self) -> List[Dict[str, Any]]:
        return self.fetchall(
            """SELECT run_ref, state, stage, started_at, finished_at
               FROM WorkbenchRunJobs
               WHERE state IN ('queued', 'running')
               ORDER BY run_ref"""
        )

    def identity_clock(self) -> Any:
        return self.fetchone("SELECT singleton, revision FROM WorkbenchPlanIdentityClock WHERE singleton = 1")

    def count_filtered(
        self,
        *,
        timeline: str,
        state: str,
        date_from: Any,
        date_to: Any,
    ) -> int:
        where_sql, params = _where_clause(timeline, state, date_from, date_to)
        return self.fetchvalue(
            f"""SELECT COUNT(*)
                FROM WorkbenchHistoryEntries e
                LEFT JOIN WorkbenchRunJobs j
                  ON e.source_kind = 'run' AND e.state = 'queued' AND j.run_ref = e.run_ref
                WHERE {where_sql}""",
            tuple(params),
        )

    def query_entries(
        self,
        *,
        timeline: str,
        state: str,
        date_from: Any,
        date_to: Any,
        order: str,
        limit: Any = None,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        where_sql, params = _where_clause(timeline, state, date_from, date_to)
        order_sql = _order_clause(order)
        limit_sql = ""
        if limit is not None:
            limit_sql = " LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        cte_sql = _RUN_ORDINALS_CTE if timeline == "run" else ""
        ro_join = (
            "LEFT JOIN run_ordinals ro ON p.source_kind = 'run' AND ro.entry_ref = p.entry_ref"
            if timeline == "run"
            else "LEFT JOIN (SELECT NULL AS entry_ref, NULL AS run_no) ro ON 0"
        )
        sql = f"""
        {cte_sql}
        SELECT {_OUTER_COLUMNS}
        FROM (
            SELECT e.*,
                   COALESCE(j.state, e.state) AS effective_state,
                   j.started_at AS live_job_started_at,
                   ROW_NUMBER() OVER (ORDER BY {order_sql}) AS _page_ord
            FROM WorkbenchHistoryEntries e
            LEFT JOIN WorkbenchRunJobs j
              ON e.source_kind = 'run' AND e.state = 'queued' AND j.run_ref = e.run_ref
            WHERE {where_sql}
            ORDER BY {order_sql}{limit_sql}
        ) p
        {ro_join}
        LEFT JOIN WorkbenchRunJobs rj ON p.run_ref IS NOT NULL AND rj.run_ref = p.run_ref
        LEFT JOIN ScheduleHistory h ON p.source_kind != 'run' AND h.version = p.plan_version
        ORDER BY p._page_ord ASC
        """
        return self.fetchall(sql, tuple(params))

    def entries_by_refs(self, entry_refs: Sequence[str]) -> Dict[str, Dict[str, Any]]:
        if not entry_refs:
            return {}
        need_runs = any(ref.startswith("run:") for ref in entry_refs)
        cte_sql = _RUN_ORDINALS_CTE if need_runs else ""
        ro_join = (
            "LEFT JOIN run_ordinals ro ON p.source_kind = 'run' AND ro.entry_ref = p.entry_ref"
            if need_runs
            else "LEFT JOIN (SELECT NULL AS entry_ref, NULL AS run_no) ro ON 0"
        )
        sql = f"""
        {cte_sql}
        SELECT {_OUTER_COLUMNS}
        FROM (
            SELECT e.*,
                   COALESCE(j.state, e.state) AS effective_state,
                   j.started_at AS live_job_started_at
            FROM WorkbenchHistoryEntries e
            LEFT JOIN WorkbenchRunJobs j
              ON e.source_kind = 'run' AND e.state = 'queued' AND j.run_ref = e.run_ref
            WHERE e.entry_ref IN (SELECT value FROM json_each(?))
        ) p
        {ro_join}
        LEFT JOIN WorkbenchRunJobs rj ON p.run_ref IS NOT NULL AND rj.run_ref = p.run_ref
        LEFT JOIN ScheduleHistory h ON p.source_kind != 'run' AND h.version = p.plan_version
        """
        return {row["entry_ref"]: row for row in self.fetchall(sql, (json.dumps(list(entry_refs)),))}

    def run_batch_quantities(self, run_ref: str) -> Dict[str, Dict[str, Any]]:
        rows = self.fetchall(
            "SELECT batch_ref, quantity FROM WorkbenchRunBatches WHERE run_ref = ?",
            (run_ref,),
        )
        return {row["batch_ref"]: {"quantity": row["quantity"]} for row in rows}

    def run_job_times(self, run_ref: str) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            "SELECT accepted_at, started_at FROM WorkbenchRunJobs WHERE run_ref = ?",
            (run_ref,),
        )

    def insert_run_entry(self, params: Sequence[Any]) -> None:
        self.conn.execute(
            """INSERT INTO WorkbenchHistoryEntries (
                entry_ref, timeline, source_kind, state,
                occurred_at, occurred_day, occurred_us, time_basis, static_label,
                run_ref, candidate_ref, scenario_ref, draft_ref,
                plan_ref, plan_version, receipt_ref, request_key,
                baseline_plan_ref, baseline_version,
                selected_candidate_ref, selection_json, times_json,
                evidence_gaps_json, objective_json,
                static_condition_digest, default_7d_calendar_digest
            ) VALUES (
                ?, 'run', 'run', ?,
                ?, ?, ?, ?, NULL,
                ?, NULL, NULL, NULL,
                NULL, NULL, NULL, ?,
                ?, ?,
                NULL, '{}', ?,
                ?, ?,
                NULL, NULL
            )""",
            tuple(params),
        )

    def update_run_entry(self, params: Sequence[Any]) -> int:
        cursor = self.conn.execute(
            """UPDATE WorkbenchHistoryEntries
            SET state = ?,
                receipt_ref = ?,
                candidate_ref = ?,
                selected_candidate_ref = ?,
                selection_json = ?,
                times_json = ?,
                evidence_gaps_json = ?,
                objective_json = ?,
                static_condition_digest = ?,
                default_7d_calendar_digest = ?
            WHERE entry_ref = ?""",
            tuple(params),
        )
        return cursor.rowcount

    def insert_official_entry(self, params: Sequence[Any]) -> None:
        self.conn.execute(
            """INSERT INTO WorkbenchHistoryEntries (
                entry_ref, timeline, source_kind, state,
                occurred_at, occurred_day, occurred_us, time_basis, static_label,
                run_ref, candidate_ref, scenario_ref, draft_ref,
                plan_ref, plan_version, receipt_ref, request_key,
                baseline_plan_ref, baseline_version,
                selected_candidate_ref, selection_json, times_json,
                evidence_gaps_json, objective_json,
                static_condition_digest, default_7d_calendar_digest
            ) VALUES (
                ?, 'official', ?, 'committed',
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, NULL, ?,
                ?, ?,
                NULL, '{}', ?,
                ?, ?,
                ?, ?
            )""",
            tuple(params),
        )
