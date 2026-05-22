from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection

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


def _candidate(item: Union[ScheduleCandidate, Dict[str, Any]]) -> ScheduleCandidate:
    return item if isinstance(item, ScheduleCandidate) else ScheduleCandidate.from_row(item)


def _candidate_row(item: Union[ScheduleCandidateRows, Dict[str, Any]]) -> ScheduleCandidateRows:
    return item if isinstance(item, ScheduleCandidateRows) else ScheduleCandidateRows.from_row(item)


def _selection(item: Union[ScheduleCandidateSelection, Dict[str, Any]]) -> ScheduleCandidateSelection:
    return item if isinstance(item, ScheduleCandidateSelection) else ScheduleCandidateSelection.from_row(item)


def _require_text(value: str, *, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field} is required")
    return text


class ScheduleCandidateRepository(BaseRepository):
    """候选方案摘要、代表明细和角色映射仓库。"""

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

    def list_candidates_by_version(self, version: int) -> List[ScheduleCandidate]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_CANDIDATE_COLUMNS)}
            FROM ScheduleCandidate
            WHERE version = ?
            ORDER BY id
            """,
            (int(version),),
        )
        return [ScheduleCandidate.from_row(row) for row in rows]

    def create_candidate(self, candidate: Union[ScheduleCandidate, Dict[str, Any]]) -> ScheduleCandidate:
        item = _candidate(candidate)
        key = _require_text(item.candidate_key, field="candidate_key")
        label = _require_text(item.candidate_label, field="candidate_label")
        kind = _require_text(item.candidate_kind, field="candidate_kind")
        status = _require_text(item.status, field="status")
        cur = self.execute(
            """
            INSERT INTO ScheduleCandidate (
                version, candidate_key, candidate_label, candidate_kind, status, graph_enabled,
                weight_level, weight_count, critical_weight, impact_weight, downstream_weight,
                sort_strategy, dispatch_mode, dispatch_rule, objective,
                score_json, metrics_json, health_json, summary_json,
                selection_reason, failure_reason, detail_saved, elapsed_ms, started_at, finished_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(item.version),
                key,
                label,
                kind,
                status,
                item.graph_enabled,
                item.weight_level,
                item.weight_count,
                item.critical_weight,
                item.impact_weight,
                item.downstream_weight,
                item.sort_strategy,
                item.dispatch_mode,
                item.dispatch_rule,
                item.objective,
                item.score_json,
                item.metrics_json,
                item.health_json,
                item.summary_json,
                item.selection_reason,
                item.failure_reason,
                item.detail_saved,
                item.elapsed_ms,
                item.started_at,
                item.finished_at,
            ),
        )
        item.id = int(cur.lastrowid) if cur.lastrowid is not None else item.id
        return item

    def create_candidates(self, candidates: Sequence[Union[ScheduleCandidate, Dict[str, Any]]]) -> Dict[str, int]:
        ids: Dict[str, int] = {}
        for candidate in candidates:
            created = self.create_candidate(candidate)
            if created.id is None:
                raise RuntimeError("候选方案写入后没有返回 id")
            ids[created.candidate_key] = int(created.id)
        return ids

    def bulk_create_candidate_rows(self, rows: Sequence[Union[ScheduleCandidateRows, Dict[str, Any]]]) -> int:
        params = []
        for row in rows:
            item = _candidate_row(row)
            params.append(
                (
                    int(item.version),
                    int(item.candidate_id),
                    int(item.op_id),
                    item.machine_id,
                    item.operator_id,
                    item.start_time,
                    item.end_time,
                    item.lock_status,
                )
            )
        cur = self.executemany(
            """
            INSERT INTO ScheduleCandidateRows (
                version, candidate_id, op_id, machine_id, operator_id, start_time, end_time, lock_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            params,
        )
        return cur.rowcount

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

    def create_selection(
        self, selection: Union[ScheduleCandidateSelection, Dict[str, Any]]
    ) -> ScheduleCandidateSelection:
        item = _selection(selection)
        role = _require_text(item.role, field="role")
        source_table = _require_text(item.source_table, field="source_table")
        cur = self.execute(
            """
            INSERT INTO ScheduleCandidateSelection (version, role, candidate_id, source_table)
            VALUES (?, ?, ?, ?)
            """,
            (int(item.version), role, int(item.candidate_id), source_table),
        )
        item.id = int(cur.lastrowid) if cur.lastrowid is not None else item.id
        return item

    def list_selections(self, version: int) -> List[ScheduleCandidateSelection]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_SELECTION_COLUMNS)}
            FROM ScheduleCandidateSelection
            WHERE version = ?
            ORDER BY
                CASE role
                    WHEN 'adopted' THEN 1
                    WHEN 'baseline_best' THEN 2
                    WHEN 'critical_best' THEN 3
                    ELSE 99
                END
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

    def delete_by_version(self, version: int) -> None:
        self.execute("DELETE FROM ScheduleCandidate WHERE version = ?", (int(version),))

    def delete_without_schedule_history(self) -> int:
        cur = self.execute(
            """
            DELETE FROM ScheduleCandidate
            WHERE NOT EXISTS (
                SELECT 1
                FROM ScheduleHistory h
                WHERE h.version = ScheduleCandidate.version
            )
            """
        )
        return int(cur.rowcount or 0)
