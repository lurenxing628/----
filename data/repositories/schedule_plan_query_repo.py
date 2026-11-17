from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Mapping, Optional, Tuple, cast

from core.shared.local_datetime import (
    datetime_to_us,
    format_local_datetime,
    us_to_datetime,
    us_to_iso,
)

from .base_repo import BaseRepository
from .schedule_detail_query import build_schedule_detail_sql
from .schedule_rows import ScheduleDetailRow, ScheduleTimeSpanRow

HISTORY_HEADER_COLUMNS = (
    "version, plan_ref, +schedule_time AS schedule_time, adopted_at, strategy, "
    "batch_count, op_count, result_status, created_by, request_key, declared_operator, "
    "application_operator, reason, source_kind, source_ref, source_label, run_ref, "
    "draft_ref, accepted_at, finished_at, algorithm_json, baseline_version, baseline_ref, "
    "baseline_kind, baseline_captured_at, baseline_captured_task_count, material_policy_json, "
    "deferred_operation_ids_json, operation_effort_json, plan_start_time, plan_end_time, "
    "end_includes_point, gantt_node_count"
)

_SCHEDULE_SELF_CONTAINED_COLUMNS = (
    "s.id, s.id AS schedule_id, s.version, s.task_ref, s.op_id, s.operation_ref, "
    "s.start_time, s.end_time, s.start_us, s.end_us, s.is_point_event, "
    "s.batch_id, s.batch_priority, s.piece_id, s.seq, "
    "s.op_type_name, s.op_type_ref, s.op_type_label, s.source, "
    "s.setup_hours, s.unit_hours, s.quantity, s.remaining_quantity, s.batch_quantity, "
    "s.quantity_basis, s.quantity_reason, "
    "s.machine_id, s.machine_ref, s.machine_label, "
    "s.operator_id, s.operator_ref, s.operator_label, "
    "s.supplier_id, s.supplier_ref, s.supplier_label, "
    "s.lock_status, +s.created_at AS created_at, "
    "m.name AS live_machine_name, op.name AS live_operator_name"
)

_SCHEDULE_LIVE_JOINS = (
    "FROM Schedule s "
    "LEFT JOIN Machines m ON m.machine_id = s.machine_id "
    "LEFT JOIN Operators op ON op.operator_id = s.operator_id"
)

RANGE_OVERLAP_SQL = (
    "((s.is_point_event = 0 AND s.start_us < ? AND s.end_us > ?) "
    "OR (s.is_point_event = 1 AND s.start_us >= ? AND s.start_us < ?))"
)


def plan_time_span(version: int, row: Optional[Mapping[str, Any]]) -> Optional[ScheduleTimeSpanRow]:
    """The span of one ScheduleHistory header; None when the header is missing or the plan has no operations."""
    if row is None or row["op_count"] == 0:
        return None
    return {
        "version": version,
        "start_time": str(row["plan_start_time"]),
        "end_time": str(row["plan_end_time"]),
        "end_includes_point": bool(row["end_includes_point"]),
    }


def _range_where(
    version: int,
    range_start_us: Optional[int],
    range_end_us: Optional[int],
) -> Tuple[str, List[Any]]:
    if range_start_us is None and range_end_us is None:
        return "s.version = ?", [int(version)]
    start_us = int(cast(int, range_start_us))
    end_us = int(cast(int, range_end_us))
    return (
        f"s.version = ? AND {RANGE_OVERLAP_SQL}",
        [int(version), end_us, start_us, start_us, end_us],
    )


class SchedulePlanQueryRepository(BaseRepository):
    """按正式排产版本读取结构化排产头与自足明细。"""

    def latest_version(self) -> Optional[int]:
        return self.fetchvalue("SELECT MAX(version) FROM ScheduleHistory WHERE version > 0", default=None)

    def get_history_row(self, version: int) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            f"SELECT {HISTORY_HEADER_COLUMNS} FROM ScheduleHistory WHERE version = ?",
            (int(version),),
        )

    def get_gantt_graph_json(self, version: int) -> Optional[str]:
        return self.fetchvalue(
            "SELECT gantt_graph_json FROM ScheduleHistory WHERE version = ?",
            (int(version),),
            default=None,
        )

    def get_first_plan_identity_row(
        self,
        *,
        version: int,
    ) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            "SELECT id AS source_row_id FROM Schedule WHERE version = ? LIMIT 1",
            (int(version),),
        )

    def get_plan_time_span(
        self,
        *,
        version: int,
    ) -> Optional[ScheduleTimeSpanRow]:
        normalized = int(version)
        row = self.fetchone(
            """
            SELECT op_count, plan_start_time, plan_end_time, end_includes_point
            FROM ScheduleHistory
            WHERE version = ?
            """,
            (normalized,),
        )
        return plan_time_span(normalized, row)

    def count_and_span(
        self,
        *,
        version: int,
        range_start_us: Optional[int] = None,
        range_end_us: Optional[int] = None,
    ) -> Dict[str, Any]:
        normalized = int(version)
        if range_start_us is None and range_end_us is None:
            head = self.get_history_row(normalized)
            if head is None or head["op_count"] == 0:
                return {
                    "total": 0,
                    "start_time": None,
                    "end_time": None,
                }
            return {
                "total": head["op_count"],
                "start_time": str(head["plan_start_time"]),
                "end_time": str(head["plan_end_time"]),
            }

        start_us = int(cast(int, range_start_us))
        end_us = int(cast(int, range_end_us))
        row = cast(
            Dict[str, Any],
            self.fetchone(
                f"""
                SELECT
                    COUNT(*) AS total,
                    MIN(s.start_us) AS min_start_us,
                    MAX(s.end_us) AS max_end_us
                FROM Schedule s
                WHERE s.version = ? AND {RANGE_OVERLAP_SQL}
                """,
                (normalized, end_us, start_us, start_us, end_us),
            ),
        )
        total = row["total"]
        if total == 0:
            return {
                "total": 0,
                "start_time": None,
                "end_time": None,
            }
        return {
            "total": total,
            "start_time": us_to_iso(row["min_start_us"]),
            "end_time": us_to_iso(row["max_end_us"]),
        }

    def list_schedule_page(
        self,
        *,
        version: int,
        range_start_us: Optional[int],
        range_end_us: Optional[int],
        limit: int,
        offset: int,
    ) -> List[Dict[str, Any]]:
        where_sql, params = _range_where(version, range_start_us, range_end_us)
        params.extend([int(limit), int(offset)])
        return self.fetchall(
            f"""
            SELECT {_SCHEDULE_SELF_CONTAINED_COLUMNS}
            {_SCHEDULE_LIVE_JOINS}
            WHERE {where_sql}
            ORDER BY s.start_us ASC, s.id ASC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )

    def list_schedule_rows(
        self,
        *,
        version: int,
        range_start_us: Optional[int] = None,
        range_end_us: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        where_sql, params = _range_where(version, range_start_us, range_end_us)
        return self.fetchall(
            f"""
            SELECT {_SCHEDULE_SELF_CONTAINED_COLUMNS}
            {_SCHEDULE_LIVE_JOINS}
            WHERE {where_sql}
            ORDER BY s.start_us ASC, s.id ASC
            """,
            tuple(params),
        )

    def get_schedule_row_by_task_ref(
        self,
        version: int,
        task_ref: str,
    ) -> Optional[Dict[str, Any]]:
        return self.fetchone(
            f"""
            SELECT {_SCHEDULE_SELF_CONTAINED_COLUMNS}
            {_SCHEDULE_LIVE_JOINS}
            WHERE s.version = ? AND s.task_ref = ?
            LIMIT 1
            """,
            (version, task_ref),
        )

    def list_schedule_rows_by_batch(
        self,
        version: int,
        batch_id: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        return self.fetchall(
            f"""
            SELECT {_SCHEDULE_SELF_CONTAINED_COLUMNS}
            {_SCHEDULE_LIVE_JOINS}
            WHERE s.version = ? AND s.batch_id = ?
            ORDER BY s.start_us ASC, s.id ASC
            LIMIT ?
            """,
            (version, batch_id, limit),
        )

    def list_detail_rows_between(
        self,
        *,
        version: int,
        start: datetime,
        end: datetime,
    ) -> List[ScheduleDetailRow]:
        start_us = datetime_to_us(start)
        end_us = datetime_to_us(end)
        sql = build_schedule_detail_sql(
            where_clauses=["s.version = ?", RANGE_OVERLAP_SQL],
        )
        return cast(
            List[ScheduleDetailRow],
            self.fetchall(sql, (int(version), end_us, start_us, start_us, end_us)),
        )

    def list_overdue_base_rows(
        self,
        *,
        version: int,
    ) -> List[Dict[str, Any]]:
        """每批在该版本里最晚的结束时刻即计划完工；零工时点事件（开工即完工）照样计入。"""
        sql = """
            SELECT
              b.batch_id AS batch_id,
              b.part_no AS part_no,
              b.part_name AS part_name,
              b.quantity AS quantity,
              CAST(b.due_date AS TEXT) AS due_date,
              MAX(s.end_us) AS max_end_us
            FROM Batches b
            LEFT JOIN BatchOperations bo ON bo.batch_id = b.batch_id
            LEFT JOIN Schedule s ON s.op_id = bo.id AND s.version = ?
            WHERE b.due_date IS NOT NULL AND TRIM(CAST(b.due_date AS TEXT)) <> ''
            GROUP BY b.batch_id
            ORDER BY b.due_date ASC, b.batch_id ASC
        """
        rows = self.fetchall(sql, (int(version),))
        for row in rows:
            max_end_us = row.pop("max_end_us")
            row["finish_time"] = (
                format_local_datetime(us_to_datetime(max_end_us))
                if max_end_us is not None
                else None
            )
        return rows
