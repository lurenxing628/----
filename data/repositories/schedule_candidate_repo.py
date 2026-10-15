from __future__ import annotations

from typing import List, Optional, Sequence

from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.models.schedule_plan_role import plan_role_order_sql

from .base_repo import BaseRepository

_CANDIDATE_COLUMNS = (
    "id",
    "version",
    "candidate_key",
    "candidate_label",
    "candidate_kind",
    "status",
    "graph_enabled",
    "weight_level",
    "weight_count",
    "critical_weight",
    "impact_weight",
    "downstream_weight",
    "sort_strategy",
    "dispatch_mode",
    "dispatch_rule",
    "objective",
    "score_json",
    "metrics_json",
    "health_json",
    "summary_json",
    "selection_reason",
    "failure_reason",
    "detail_saved",
    "elapsed_ms",
    "started_at",
    "finished_at",
    "created_at",
)

_CANDIDATE_ROW_COLUMNS = (
    "id",
    "version",
    "candidate_id",
    "op_id",
    "machine_id",
    "operator_id",
    "start_time",
    "end_time",
    "lock_status",
    "created_at",
)

_SELECTION_COLUMNS = (
    "id",
    "version",
    "role",
    "candidate_id",
    "source_table",
    "created_at",
)


def _columns_sql(columns: Sequence[str]) -> str:
    return ", ".join(columns)


class ScheduleCandidateRepository(BaseRepository):
    """历史候选摘要、明细和角色映射的只读仓库。"""

    def get_candidate(self, candidate_id: int) -> Optional[ScheduleCandidate]:
        row = self.fetchone(
            f"SELECT {_columns_sql(_CANDIDATE_COLUMNS)} FROM ScheduleCandidate WHERE id = ?",
            (int(candidate_id),),
        )
        return ScheduleCandidate.from_row(row) if row else None

    def get_candidate_by_key(self, *, version: int, candidate_key: str) -> Optional[ScheduleCandidate]:
        row = self.fetchone(
            f"""
            SELECT {_columns_sql(_CANDIDATE_COLUMNS)}
            FROM ScheduleCandidate
            WHERE version = ? AND candidate_key = ?
            """,
            (int(version), str(candidate_key)),
        )
        return ScheduleCandidate.from_row(row) if row else None

    def list_candidate_rows(self, *, version: int, candidate_id: int) -> List[ScheduleCandidateRows]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_CANDIDATE_ROW_COLUMNS)}
            FROM ScheduleCandidateRows
            WHERE version = ? AND candidate_id = ?
            ORDER BY start_time, id
            """,
            (int(version), int(candidate_id)),
        )
        return [ScheduleCandidateRows.from_row(row) for row in rows]

    def list_selections(self, version: int) -> List[ScheduleCandidateSelection]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_SELECTION_COLUMNS)}
            FROM ScheduleCandidateSelection
            WHERE version = ?
            ORDER BY {plan_role_order_sql()}
            """,
            (int(version),),
        )
        return [ScheduleCandidateSelection.from_row(row) for row in rows]

    def get_selection(self, *, version: int, role: str) -> Optional[ScheduleCandidateSelection]:
        row = self.fetchone(
            f"""
            SELECT {_columns_sql(_SELECTION_COLUMNS)}
            FROM ScheduleCandidateSelection
            WHERE version = ? AND role = ?
            """,
            (int(version), str(role)),
        )
        return ScheduleCandidateSelection.from_row(row) if row else None
