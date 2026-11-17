"""Request-local, SELECT-only catalog pages over structured ScheduleHistory headers."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .schedule_plan_query_repo import HISTORY_HEADER_COLUMNS, SchedulePlanQueryRepository, plan_time_span
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


class WorkbenchPlanCatalogRepository(SchedulePlanQueryRepository):
    """Transaction-local header and existence cache for one catalog or plan read."""

    def __init__(self, conn: sqlite3.Connection, logger=None):
        super().__init__(conn, logger=logger)
        self._histories: Dict[int, Optional[Dict[str, Any]]] = {}
        self._versions_by_ref: Dict[str, int] = {}
        self._first_row_ids: Dict[int, Optional[Dict[str, Any]]] = {}
        self._latest_version: Optional[int] = None
        self._latest_version_loaded = False

    def _cache_history_row(self, row: Dict[str, Any]) -> None:
        version = row["version"]
        self._histories[version] = row
        self._versions_by_ref[str(row["plan_ref"])] = version

    def cached_version_by_ref(self, plan_ref: str) -> Optional[int]:
        return self._versions_by_ref.get(plan_ref)

    def cached_plan_ref_by_version(self, version: int) -> Optional[str]:
        row = self._histories.get(int(version))
        return str(row["plan_ref"]) if row is not None else None

    def latest_version(self) -> Optional[int]:
        if not self._latest_version_loaded:
            row = self.fetchone("SELECT version FROM ScheduleHistory WHERE version > 0 ORDER BY version DESC LIMIT 1")
            self._latest_version = row["version"] if row else None
            self._latest_version_loaded = True
        return self._latest_version

    def get_history_row(self, version: int) -> Optional[Dict[str, Any]]:
        normalized = int(version)
        if normalized not in self._histories:
            row = self.fetchone(
                f"SELECT {HISTORY_HEADER_COLUMNS} FROM ScheduleHistory WHERE version = ?",
                (normalized,),
            )
            if row is not None:
                self._cache_history_row(row)
            else:
                self._histories[normalized] = None
        return self._histories[normalized]

    def prefetch_history_rows(self, versions: Sequence[int]) -> None:
        missing = [int(v) for v in dict.fromkeys(versions) if int(v) not in self._histories]
        if not missing:
            return
        self._histories.update((v, None) for v in missing)
        rows = self.fetchall(
            f"SELECT {HISTORY_HEADER_COLUMNS} FROM ScheduleHistory "
            "WHERE version IN (SELECT value FROM json_each(?)) ORDER BY version DESC",
            (json.dumps(missing),),
        )
        for row in rows:
            self._cache_history_row(row)
        self._prefetch_first_row_ids(missing)

    def _prefetch_first_row_ids(self, versions: Sequence[int]) -> None:
        missing = [int(v) for v in dict.fromkeys(versions) if int(v) not in self._first_row_ids]
        if not missing:
            return
        self._first_row_ids.update((v, None) for v in missing)
        rows = self.fetchall(
            """
            SELECT
                CAST(v.value AS INTEGER) AS version,
                (SELECT s.id FROM Schedule s WHERE s.version = CAST(v.value AS INTEGER) LIMIT 1) AS source_row_id
            FROM json_each(?) AS v
            """,
            (json.dumps(missing),),
        )
        for row in rows:
            if row["source_row_id"] is not None:
                self._first_row_ids[row["version"]] = {"source_row_id": row["source_row_id"]}

    def get_first_plan_identity_row(self, *, version: int) -> Optional[Dict[str, Any]]:
        normalized = int(version)
        if normalized not in self._first_row_ids:
            self._first_row_ids[normalized] = super().get_first_plan_identity_row(version=normalized)
        return self._first_row_ids[normalized]

    def get_plan_time_span(self, *, version: int) -> Optional[ScheduleTimeSpanRow]:
        normalized = int(version)
        return plan_time_span(normalized, self.get_history_row(normalized))

    def history_page(
        self, *, page_size: int, before_version: Optional[int],
    ) -> Tuple[List[Dict[str, Any]], bool]:
        validate_page_size(page_size)
        validate_before_version(before_version)
        where, params = ("", []) if before_version is None else ("WHERE version < ?", [before_version])
        fetched = self.fetchall(
            f"SELECT {HISTORY_HEADER_COLUMNS} FROM ScheduleHistory {where} ORDER BY version DESC LIMIT ?",
            params + [page_size + 1],
        )
        rows = fetched[:page_size]
        page_versions = [row["version"] for row in rows]
        for row in rows:
            self._cache_history_row(row)
        self._prefetch_first_row_ids(page_versions)
        return rows, len(fetched) > page_size
