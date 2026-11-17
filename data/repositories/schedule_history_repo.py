from __future__ import annotations

from typing import Any, Mapping, cast

from .base_repo import BaseRepository

_INSERT_COLUMNS = (
    "version",
    "plan_ref",
    "adopted_at",
    "strategy",
    "batch_count",
    "op_count",
    "result_status",
    "created_by",
    "request_key",
    "declared_operator",
    "application_operator",
    "reason",
    "source_kind",
    "source_ref",
    "source_label",
    "run_ref",
    "draft_ref",
    "accepted_at",
    "finished_at",
    "algorithm_json",
    "baseline_version",
    "baseline_ref",
    "baseline_kind",
    "baseline_captured_at",
    "baseline_captured_task_count",
    "material_policy_json",
    "deferred_operation_ids_json",
    "operation_effort_json",
    "plan_start_time",
    "plan_end_time",
    "end_includes_point",
    "gantt_node_count",
    "gantt_graph_json",
)

_INSERT_SQL = (
    "INSERT INTO ScheduleHistory ("
    + ", ".join(_INSERT_COLUMNS)
    + ") VALUES ("
    + ", ".join("?" for _ in _INSERT_COLUMNS)
    + ")"
)


class ScheduleHistoryRepository(BaseRepository):
    """排产历史仓库（ScheduleHistory）。"""

    def allocate_next_version(self) -> int:
        """
        原子分配排产版本号（避免并发下 MAX(version)+1 复用）。

        版本号只由这里从 `ScheduleVersionSeq` 自增表分配（version=PRIMARY KEY AUTOINCREMENT），
        所以 ScheduleHistory 的版本号不会超过序列表。允许“跳号”（例如落库失败/回滚），但保证不会复用。
        """
        cur = self.execute("INSERT INTO ScheduleVersionSeq DEFAULT VALUES")
        return cast(int, cur.lastrowid)

    def create(self, payload: Mapping[str, Any]) -> str:
        """Insert one plan head; returns the ``schedule_time`` the database stamped on it."""
        rows = self.execute(
            _INSERT_SQL + " RETURNING schedule_time",
            tuple(payload[col] for col in _INSERT_COLUMNS),
        ).fetchall()
        return rows[0][0]
