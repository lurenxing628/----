from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Union

from core.models.schedule_adjustment import (
    ScheduleAdjustmentScenario,
    ScheduleAdjustmentScenarioRow,
)

from .base_repo import BaseRepository

_SCENARIO_COLUMNS = (
    "scenario_id",
    "source_draft_id",
    "base_version",
    "base_plan_role",
    "base_source_table",
    "base_candidate_id",
    "base_candidate_key",
    "scenario_name",
    "status",
    "validation_status",
    "issue_count",
    "issues_json",
    "row_count",
    "created_by",
    "published_version",
    "published_by",
    "published_reason",
    "published_at",
    "created_at",
    "updated_at",
)

_ROW_COLUMNS = (
    "id",
    "scenario_id",
    "source_table",
    "source_row_id",
    "op_id",
    "machine_id",
    "operator_id",
    "start_time",
    "end_time",
    "lock_status",
    "is_changed",
    "change_summary_json",
    "created_at",
)


def _columns_sql(columns: Sequence[str]) -> str:
    return ", ".join(columns)


def _scenario(item: Union[ScheduleAdjustmentScenario, Dict[str, Any]]) -> ScheduleAdjustmentScenario:
    return item if isinstance(item, ScheduleAdjustmentScenario) else ScheduleAdjustmentScenario.from_row(item)


def _scenario_row(item: Union[ScheduleAdjustmentScenarioRow, Dict[str, Any]]) -> ScheduleAdjustmentScenarioRow:
    return item if isinstance(item, ScheduleAdjustmentScenarioRow) else ScheduleAdjustmentScenarioRow.from_row(item)


class ScheduleAdjustmentScenarioRepository(BaseRepository):
    """甘特图模拟方案仓库，只读写 Scenario 表。"""

    def get_scenario(self, scenario_id: str) -> Optional[ScheduleAdjustmentScenario]:
        row = self.fetchone(
            f"SELECT {_columns_sql(_SCENARIO_COLUMNS)} FROM ScheduleAdjustmentScenario WHERE scenario_id = ?",
            (str(scenario_id),),
        )
        return ScheduleAdjustmentScenario.from_row(row) if row else None

    def get_scenario_by_draft(self, draft_id: str) -> Optional[ScheduleAdjustmentScenario]:
        row = self.fetchone(
            f"SELECT {_columns_sql(_SCENARIO_COLUMNS)} FROM ScheduleAdjustmentScenario WHERE source_draft_id = ?",
            (str(draft_id),),
        )
        return ScheduleAdjustmentScenario.from_row(row) if row else None

    def create_scenario(
        self,
        scenario: Union[ScheduleAdjustmentScenario, Dict[str, Any]],
        rows: Sequence[Union[ScheduleAdjustmentScenarioRow, Dict[str, Any]]],
    ) -> ScheduleAdjustmentScenario:
        item = _scenario(scenario)
        row_items = [_scenario_row(row) for row in rows]
        self.execute(
            """
            INSERT INTO ScheduleAdjustmentScenario (
                scenario_id, source_draft_id, base_version, base_plan_role,
                base_source_table, base_candidate_id, base_candidate_key,
                scenario_name, status, validation_status, issue_count,
                issues_json, row_count, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.scenario_id,
                item.source_draft_id,
                int(item.base_version),
                item.base_plan_role,
                item.base_source_table,
                item.base_candidate_id,
                item.base_candidate_key,
                item.scenario_name,
                item.status,
                item.validation_status,
                int(item.issue_count),
                item.issues_json,
                len(row_items),
                item.created_by,
            ),
        )
        self._insert_rows(item.scenario_id, row_items)
        created = self.get_scenario(item.scenario_id)
        if created is None:
            raise RuntimeError("模拟方案写入后没有返回记录")
        return created

    def list_rows(self, scenario_id: str) -> List[ScheduleAdjustmentScenarioRow]:
        rows = self.fetchall(
            f"""
            SELECT {_columns_sql(_ROW_COLUMNS)}
            FROM ScheduleAdjustmentScenarioRow
            WHERE scenario_id = ?
            ORDER BY start_time, id
            """,
            (str(scenario_id),),
        )
        return [ScheduleAdjustmentScenarioRow.from_row(row) for row in rows]

    def mark_published(
        self,
        *,
        scenario_id: str,
        new_version: int,
        published_by: str,
        reason: str,
    ) -> Optional[ScheduleAdjustmentScenario]:
        cur = self.execute(
            """
            UPDATE ScheduleAdjustmentScenario
            SET status = 'published',
                published_version = ?,
                published_by = ?,
                published_reason = ?,
                published_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE scenario_id = ?
              AND status = 'active'
              AND published_version IS NULL
            """,
            (int(new_version), str(published_by), str(reason), str(scenario_id)),
        )
        if int(cur.rowcount or 0) != 1:
            return None
        scenario = self.get_scenario(scenario_id)
        if scenario is None:
            raise RuntimeError(f"模拟方案不存在：{scenario_id}")
        return scenario

    def _insert_rows(self, scenario_id: str, rows: Sequence[ScheduleAdjustmentScenarioRow]) -> None:
        self.executemany(
            """
            INSERT INTO ScheduleAdjustmentScenarioRow (
                scenario_id, source_table, source_row_id, op_id, machine_id,
                operator_id, start_time, end_time, lock_status, is_changed,
                change_summary_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    str(scenario_id),
                    row.source_table,
                    row.source_row_id,
                    int(row.op_id),
                    row.machine_id,
                    row.operator_id,
                    row.start_time,
                    row.end_time,
                    row.lock_status,
                    row.is_changed,
                    row.change_summary_json,
                )
                for row in rows
            ],
        )
