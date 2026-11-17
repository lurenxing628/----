"""现场（报工文件 / 现场工作台）只读事实：可用设备人员索引、计划结合 OperationExecutionStates 的双口径汇总与索引真分页。"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple

from core.models.hours import HourTotals, public_hours, stored_exact_hours, sum_hours
from core.shared.local_datetime import datetime_to_us

from .base_repo import BaseRepository
from .schedule_plan_query_repo import RANGE_OVERLAP_SQL

STATES = ("unreported", "started", "partial", "complete")

_SEARCHABLE_SQL = """instr(
    aps_casefold(
        s.batch_id
        || ' ' || CAST(s.seq AS TEXT) || ' ' || s.op_type_name
        || ' ' || COALESCE(pt.part_name, '')
        || CASE WHEN s.piece_id IS NOT NULL THEN ' ' || s.piece_id ELSE '' END
        || CASE WHEN pm_ref.ref IS NOT NULL THEN ' ' || COALESCE(NULLIF(pm.name, ''), s.machine_id) ELSE '' END
        || CASE WHEN po_ref.ref IS NOT NULL THEN ' ' || COALESCE(NULLIF(po.name, ''), s.operator_id) ELSE '' END
        || COALESCE((
            SELECT ' ' || group_concat(r_tok, ' ')
            FROM (
                SELECT p.report_no
                    || CASE WHEN am_ref.ref IS NOT NULL THEN ' ' || CASE WHEN am_ref.active = 1 AND am.name IS NOT NULL AND am.name != '' THEN am.name ELSE am_ref.entity_key END ELSE '' END
                    || CASE WHEN ao_ref.ref IS NOT NULL THEN ' ' || CASE WHEN ao_ref.active = 1 AND ao.name IS NOT NULL AND ao.name != '' THEN ao.name ELSE ao_ref.entity_key END ELSE '' END
                    AS r_tok
                FROM WorkbenchProductionReports p
                LEFT JOIN WorkbenchEntityRefs am_ref ON am_ref.ref = p.actual_machine_ref
                LEFT JOIN Machines am ON am_ref.kind = 'machine' AND am_ref.active = 1 AND am.machine_id = am_ref.entity_key
                LEFT JOIN WorkbenchEntityRefs ao_ref ON ao_ref.ref = p.actual_operator_ref
                LEFT JOIN Operators ao ON ao_ref.kind = 'operator' AND ao_ref.active = 1 AND ao.operator_id = ao_ref.entity_key
                WHERE p.voided = 0 AND p.operation_ref = s.operation_ref
                ORDER BY p.recorded_at, p.report_no
            )
        ), '')
    ),
    ?
) > 0"""


def _range_clauses(version: int, scope: Mapping[str, Any]) -> Tuple[List[str], List[Any]]:
    clauses = ["s.version = ?"]
    params: List[Any] = [version]
    if scope.get("range_start"):
        start_us = datetime_to_us(datetime.fromisoformat(scope["range_start"]))
        end_us = datetime_to_us(datetime.fromisoformat(scope["range_end"]))
        clauses.append(RANGE_OVERLAP_SQL)
        params.extend([end_us, start_us, start_us, end_us])
    return clauses, params


def _evaluated_cte_sql(version: int, scope: Mapping[str, Any]) -> Tuple[str, List[Any]]:
    clauses, params = _range_clauses(version, scope)
    if scope.get("plan_finish_date_from"):
        start_d = date.fromisoformat(scope["plan_finish_date_from"])
        end_d = date.fromisoformat(scope["plan_finish_date_to"])
        finish_from_us = datetime_to_us(datetime(start_d.year, start_d.month, start_d.day))
        finish_to_inclusive_us = datetime_to_us(
            datetime(end_d.year, end_d.month, end_d.day, 23, 59, 59, 999999)
        )
        clauses.append("s.end_us >= ? AND s.end_us <= ?")
        params.extend([finish_from_us, finish_to_inclusive_us])
    if scope.get("batch_ids"):
        clauses.append("s.batch_id IN (SELECT value FROM json_each(?))")
        params.append(json.dumps(scope["batch_ids"]))
    if scope.get("resource_ref"):
        ref = scope["resource_ref"]
        if scope["resource_type"] == "machine":
            clauses.append(
                "(pm_ref.ref = ? OR EXISTS ("
                "SELECT 1 FROM WorkbenchProductionReports p "
                "WHERE p.voided = 0 AND p.actual_machine_ref = ? AND p.operation_ref = s.operation_ref))"
            )
        else:
            clauses.append(
                "(po_ref.ref = ? OR EXISTS ("
                "SELECT 1 FROM WorkbenchProductionReports p "
                "WHERE p.voided = 0 AND p.actual_operator_ref = ? AND p.operation_ref = s.operation_ref))"
            )
        params.extend([ref, ref])
    has_query = bool(scope.get("query"))
    if has_query:
        clauses.append(_SEARCHABLE_SQL)
        params.append(scope["query"].casefold())
    resource_name_joins = (
        "LEFT JOIN Machines pm ON pm.machine_id = s.machine_id "
        "LEFT JOIN Operators po ON po.operator_id = s.operator_id"
        if has_query
        else ""
    )
    where_sql = " AND ".join(clauses)
    cte_sql = f"""
    WITH raw_tasks AS (
        SELECT
            s.task_ref,
            s.operation_ref,
            s.batch_id,
            s.piece_id,
            s.seq,
            s.op_type_name,
            s.start_us,
            s.end_us,
            s.is_point_event,
            s.quantity,
            s.batch_quantity,
            s.quantity_basis,
            s.quantity_reason,
            pt.part_name,
            pm_ref.ref AS planned_machine_ref,
            po_ref.ref AS planned_operator_ref,
            o.active AS identity_active,
            bo.id AS live_op_id,
            bo.source AS live_source,
            CASE
                WHEN bo.piece_id IS NOT NULL AND bo.piece_id != '' THEN 1
                ELSE b.quantity
            END AS target_qty,
            COALESCE(oes.active_report_count, 0) AS rep_cnt,
            COALESCE(oes.known_completed_quantity, 0) AS known_qty,
            COALESCE(oes.unknown_quantity_count, 0) AS unk_qty,
            CASE
                WHEN bo.source = 'external' THEN COALESCE(oes.external_complete_flag, 0)
                ELSE COALESCE(oes.internal_complete_flag, 0)
            END AS records_complete,
            COALESCE(oes.any_actual_end, 0) AS any_end,
            oes.known_effective_hours_text,
            COALESCE(oes.unknown_hour_count, 0) AS unk_hours
        FROM Schedule s
        JOIN WorkbenchPlanSourceRefs o
          ON o.kind = 'operation' AND o.ref = s.operation_ref
        LEFT JOIN BatchOperations bo
          ON o.active = 1
         AND bo.id = CAST(o.source_key AS INTEGER)
         AND CAST(bo.id AS TEXT) = o.source_key
        LEFT JOIN Batches b ON b.batch_id = bo.batch_id
        LEFT JOIN Batches sb ON sb.batch_id = s.batch_id
        LEFT JOIN Parts pt ON pt.part_no = sb.part_no
        LEFT JOIN WorkbenchEntityRefs pm_ref
          ON pm_ref.kind = 'machine' AND pm_ref.active = 1 AND pm_ref.entity_key = s.machine_id
        LEFT JOIN WorkbenchEntityRefs po_ref
          ON po_ref.kind = 'operator' AND po_ref.active = 1 AND po_ref.entity_key = s.operator_id
        {resource_name_joins}
        LEFT JOIN OperationExecutionStates oes ON oes.operation_ref = s.operation_ref
        WHERE {where_sql}
    ),
    evaluated_tasks AS (
        SELECT
            ct.*,
            CASE
                WHEN ct.target_qty IS NOT NULL AND ct.known_qty = ct.target_qty AND ct.unk_qty = 0 AND ct.records_complete = 1
                THEN 'complete'
                WHEN ct.known_qty > 0 OR ct.any_end = 1
                THEN 'partial'
                WHEN ct.rep_cnt > 0
                THEN 'started'
                ELSE 'unreported'
            END AS exec_state,
            CASE
                WHEN ct.rep_cnt > 0
                 AND ct.identity_active = 1
                 AND ct.live_op_id IS NOT NULL
                 AND ct.live_source IN ('internal', 'external')
                 AND ct.target_qty IS NOT NULL
                 AND ct.records_complete = 1
                 AND ct.known_qty <= ct.target_qty
                THEN 0
                ELSE 1
            END AS is_quality_incomplete
        FROM raw_tasks ct
    )
    """
    return cte_sql, params


def empty_field_summary() -> Dict[str, Any]:
    return {
        "tasks": 0,
        "reports": 0,
        "complete": 0,
        "incomplete": 0,
        "state_counts": dict.fromkeys(STATES, 0),
        "state_scope_tasks": 0,
        "effective_processing_hours": None,
        "known_effective_processing_hours": None,
        "unknown_hour_reports": 0,
    }


class WorkbenchFieldQueryRepository(BaseRepository):
    def active_resource_index_rows(self) -> List[Dict[str, Any]]:
        """有效的设备/人员系统编号及其名称（ref, kind, entity_key, label）。"""
        return self.fetchall("""SELECT e.ref,e.kind,e.entity_key,
            CASE WHEN e.kind='machine' THEN m.name ELSE o.name END AS label
            FROM WorkbenchEntityRefs e
            LEFT JOIN Machines m ON e.kind='machine' AND m.machine_id=e.entity_key
            LEFT JOIN Operators o ON e.kind='operator' AND o.operator_id=e.entity_key
            WHERE e.active=1 AND e.kind IN ('machine','operator')""")

    def first_plan_binding_issue(self, version: int, scope: Mapping[str, Any]) -> Optional[str]:
        clauses, params = _range_clauses(version, scope)
        where_sql = " AND ".join(clauses)
        row = self.fetchone(
            f"""SELECT
                    CASE
                        WHEN b_ref.ref IS NULL
                          OR (s.machine_id IS NOT NULL AND s.machine_id != '' AND pm_ref.ref IS NULL)
                          OR (s.operator_id IS NOT NULL AND s.operator_id != '' AND po_ref.ref IS NULL)
                        THEN 'identity_missing'
                        ELSE 'operation_missing'
                    END AS issue
                FROM Schedule s
                LEFT JOIN WorkbenchPlanSourceRefs o
                  ON o.kind = 'operation' AND o.ref = s.operation_ref
                LEFT JOIN WorkbenchEntityRefs b_ref
                  ON b_ref.kind = 'batch' AND b_ref.active = 1 AND b_ref.entity_key = s.batch_id
                LEFT JOIN WorkbenchEntityRefs pm_ref
                  ON pm_ref.kind = 'machine' AND pm_ref.active = 1 AND pm_ref.entity_key = s.machine_id
                LEFT JOIN WorkbenchEntityRefs po_ref
                  ON po_ref.kind = 'operator' AND po_ref.active = 1 AND po_ref.entity_key = s.operator_id
                WHERE {where_sql}
                  AND (
                      o.ref IS NULL
                      OR b_ref.ref IS NULL
                      OR (s.machine_id IS NOT NULL AND s.machine_id != '' AND pm_ref.ref IS NULL)
                      OR (s.operator_id IS NOT NULL AND s.operator_id != '' AND po_ref.ref IS NULL)
                  )
                LIMIT 1""",
            tuple(params),
        )
        return None if row is None else row["issue"]

    def field_summary(self, version: int, scope: Mapping[str, Any]) -> Dict[str, Any]:
        cte_sql, params = _evaluated_cte_sql(version, scope)
        grouped = self.fetchall(
            cte_sql
            + """
            SELECT
                exec_state,
                COUNT(*) AS task_cnt,
                SUM(rep_cnt) AS report_cnt,
                SUM(is_quality_incomplete) AS incomplete_cnt,
                SUM(unk_hours) AS unk_hour_cnt
            FROM evaluated_tasks
            GROUP BY exec_state
            """,
            tuple(params),
        )
        if not grouped:
            return empty_field_summary()
        state_counts = dict.fromkeys(STATES, 0)
        for row in grouped:
            state_counts[row["exec_state"]] = row["task_cnt"]
        state_scope_tasks = sum(state_counts.values())
        total_reports = sum(row["report_cnt"] for row in grouped)
        unknown_hour_reports = sum(row["unk_hour_cnt"] for row in grouped)
        # Each operation keeps its known hours as one exact total; the second scan runs only when some
        # report's hours are known.
        known_rows = (
            self.fetchall(
                cte_sql
                + """
                SELECT known_effective_hours_text
                FROM evaluated_tasks
                WHERE known_effective_hours_text IS NOT NULL
                """,
                tuple(params),
            )
            if total_reports > unknown_hour_reports
            else []
        )
        hours = HourTotals(
            sum_hours(stored_exact_hours(row["known_effective_hours_text"]) for row in known_rows).known,
            unknown_hour_reports,
        )
        selected_state = scope.get("state")
        matched = [row for row in grouped if not selected_state or row["exec_state"] == selected_state]
        tasks_total = sum(row["task_cnt"] for row in matched)
        report_count = sum(row["report_cnt"] for row in matched)
        complete_count = sum(row["task_cnt"] for row in matched if row["exec_state"] == "complete")
        incomplete_count = sum(row["incomplete_cnt"] for row in matched)
        return {
            "tasks": tasks_total,
            "reports": report_count,
            "complete": complete_count,
            "incomplete": incomplete_count,
            "state_counts": state_counts,
            "state_scope_tasks": state_scope_tasks,
            "effective_processing_hours": public_hours(hours.total),
            "known_effective_processing_hours": public_hours(hours.known),
            "unknown_hour_reports": hours.unknown,
        }

    def locate_task_index(
        self, version: int, scope: Mapping[str, Any], task_ref: str
    ) -> Optional[Tuple[int, str]]:
        cte_sql, params = _evaluated_cte_sql(version, scope)
        state_where = ""
        if scope.get("state"):
            state_where = "WHERE exec_state = ?"
            params.append(scope["state"])
        params.append(task_ref)
        row = self.fetchone(
            cte_sql
            + f"""
            SELECT idx, operation_ref
            FROM (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY batch_id ASC, seq ASC, start_us ASC, task_ref ASC) - 1 AS idx,
                    task_ref,
                    operation_ref
                FROM evaluated_tasks
                {state_where}
            )
            WHERE task_ref = ?
            """,
            tuple(params),
        )
        if row is None:
            return None
        return row["idx"], row["operation_ref"]

    def field_task_rows(
        self,
        version: int,
        scope: Mapping[str, Any],
        *,
        limit: Optional[int] = None,
        offset: int = 0,
        task_ref: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        cte_sql, params = _evaluated_cte_sql(version, scope)
        outer_clauses: List[str] = []
        if scope.get("state"):
            outer_clauses.append("exec_state = ?")
            params.append(scope["state"])
        if task_ref is not None:
            outer_clauses.append("task_ref = ?")
            params.append(task_ref)
        outer_where = ("WHERE " + " AND ".join(outer_clauses)) if outer_clauses else ""
        limit_sql = ""
        if limit is not None:
            limit_sql = "LIMIT ? OFFSET ?"
            params.extend([limit, offset])
        return self.fetchall(
            cte_sql
            + f"""
            SELECT
                task_ref,
                operation_ref,
                batch_id,
                piece_id,
                seq,
                op_type_name,
                start_us,
                end_us,
                is_point_event,
                quantity,
                batch_quantity,
                quantity_basis,
                quantity_reason,
                part_name,
                planned_machine_ref,
                planned_operator_ref
            FROM evaluated_tasks
            {outer_where}
            ORDER BY batch_id ASC, seq ASC, start_us ASC, task_ref ASC
            {limit_sql}
            """,
            tuple(params),
        )
