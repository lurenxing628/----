"""Request-local, SELECT-only catalog pages using existing indexes.

History seek order is version DESC (distinct versions); the head of each selected
version is schedule_time DESC, id DESC, matching the existing identity query.
Scenario seek order is scenario_id COLLATE BINARY ASC, deliberately independent
of the full catalog's chronological order. Neither page uses OFFSET or COUNT.
One lookahead header/key is read, but its details are never inspected.

Use a fresh instance per page under the caller's read snapshot. Header, role and
span caches are request-local; no database/global cache or schema changes. The
lean history projection intentionally omits schedule_row_count: identity only
needs version/status/summary, and counting rows would touch unnecessary details.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional, Tuple

from core.models.schedule_plan_role import SOURCE_SCHEDULE

from .schedule_plan_query_repo import SchedulePlanQueryRepository
from .schedule_rows import ScheduleTimeSpanRow

DEFAULT_PLAN_PAGE_SIZE = 20
MAX_PLAN_PAGE_SIZE = 50
MAX_PLAN_VERSION = (1 << 63) - 1


def validate_page_size(value: int) -> None:
    if type(value) is not int or not 1 <= value <= MAX_PLAN_PAGE_SIZE:
        raise ValueError("目录每页数量必须是 1 到 50 的整数。")


def validate_before_version(value: Optional[int]) -> None:
    if value is not None and (type(value) is not int or not 1 <= value <= MAX_PLAN_VERSION):
        raise ValueError("历史页版本边界必须是 SQLite 范围内的正整数。")


def validate_after_scenario_id(value: Optional[str]) -> None:
    if value is not None and (not isinstance(value, str) or not value or "\x00" in value):
        raise ValueError("场景页边界必须是非空且不含空字符的内部场景编号。")


class WorkbenchPlanCatalogRepository(SchedulePlanQueryRepository):
    """Strict-query repository restricted to one catalog page, not full history."""

    def __init__(self, conn: sqlite3.Connection, logger=None):
        super().__init__(conn, logger=logger)
        self._histories: Dict[int, Optional[Dict[str, Any]]] = {}
        self._roles: Dict[int, List[Dict[str, Any]]] = {}
        self._scenarios: Dict[str, Dict[str, Any]] = {}
        self._spans: Dict[Tuple[int, str, Optional[int], Optional[str]], Optional[ScheduleTimeSpanRow]] = {}

    def latest_version(self) -> Optional[int]:
        row = self.fetchone("SELECT version FROM ScheduleHistory WHERE version > 0 ORDER BY version DESC LIMIT 1")
        return int(row["version"]) if row else None

    def history_page(
        self, *, page_size: int, before_version: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        validate_page_size(page_size)
        validate_before_version(before_version)
        where, params = ("", []) if before_version is None else ("WHERE version < ?", [before_version])
        keys = self.fetchall(
            f"SELECT DISTINCT version FROM ScheduleHistory {where} ORDER BY version DESC LIMIT ?",
            params + [page_size + 1],
        )
        rows = []
        for key in keys[:page_size]:
            row = self.get_history_identity_row(int(key["version"]))
            if row is None:
                raise RuntimeError("目录读取期间排产历史消失；调用方必须提供一致读快照。")
            rows.append(row)
        return rows, len(keys) > page_size

    def scenario_page(
        self, *, page_size: int, after_scenario_id: Optional[str],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        validate_page_size(page_size)
        validate_after_scenario_id(after_scenario_id)
        where, params = ("", []) if after_scenario_id is None else (
            "WHERE scenario_id COLLATE BINARY > ?", [after_scenario_id],
        )
        rows = self.fetchall(
            "SELECT scenario_id, source_draft_id, base_version, base_plan_role, base_source_table, "
            "base_candidate_id, base_candidate_key, scenario_name, status, validation_status, "
            "issue_count, row_count, published_version FROM ScheduleAdjustmentScenario "
            f"{where} ORDER BY scenario_id COLLATE BINARY ASC LIMIT ?",
            params + [page_size + 1],
        )
        selected = rows[:page_size]
        self._scenarios.update((str(row["scenario_id"]), row) for row in selected)
        return selected, len(rows) > page_size

    def get_history_identity_row(self, version: int) -> Optional[Dict[str, Any]]:
        if version not in self._histories:
            self._histories[version] = self.fetchone(
                "SELECT version, result_status, result_summary FROM ScheduleHistory WHERE version = ? "
                "ORDER BY schedule_time DESC, id DESC LIMIT 1", (version,),
            )
        return self._histories[version]

    def list_plan_role_options(self, version: int) -> List[Dict[str, Any]]:
        if version not in self._roles:
            self._roles[version] = super().list_plan_role_options(version)
        return self._roles[version]

    def get_scenario_context(self, scenario_id: str) -> Optional[Dict[str, Any]]:
        if scenario_id in self._scenarios:
            return self._scenarios[scenario_id]
        return super().get_scenario_context(scenario_id)

    def get_plan_time_span(
        self, *, version: int, source_table: str, candidate_id: Optional[int], scenario_id: Optional[str] = None,
    ) -> Optional[ScheduleTimeSpanRow]:
        key = (version, source_table, None if source_table == SOURCE_SCHEDULE else candidate_id, scenario_id)
        if key not in self._spans:
            self._spans[key] = super().get_plan_time_span(
                version=version, source_table=source_table, candidate_id=candidate_id, scenario_id=scenario_id,
            )
        return self._spans[key]

    def list_history_identity_rows(self) -> List[Dict[str, Any]]:
        raise RuntimeError("分页目录禁止调用全量历史查询。")
