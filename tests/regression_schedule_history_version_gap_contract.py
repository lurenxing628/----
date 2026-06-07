"""回归测试：ScheduleHistoryRepository 版本号分配与历史空洞契约。守护 allocate_next_version 通过 ScheduleVersionSeq 单调递增且已分配号不被复用——回滚未落库的版本会留下空洞（历史只剩 [1,3]），get_by_version 对未落库号返回 None，get_latest_version/list_versions 只反映真实历史；新分配器还须对齐到既有历史最大版本之上（历史含 9 时下一个分配为 10、11）。"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import List

from core.infrastructure.transaction import TransactionManager
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from tests._support.paths import REPO_ROOT


def _make_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    return conn


def _history_payload(version: int) -> dict:
    return {
        "version": int(version),
        "strategy": "priority_first",
        "batch_count": 1,
        "op_count": 1,
        "result_status": "success",
        "result_summary": "{}",
        "created_by": "pytest",
    }


def _create_history(repo: ScheduleHistoryRepository, tx_manager: TransactionManager, version: int) -> None:
    with tx_manager.transaction():
        repo.create(_history_payload(version))


def _allocate_committed(repo: ScheduleHistoryRepository, tx_manager: TransactionManager) -> int:
    with tx_manager.transaction():
        return int(repo.allocate_next_version())


def _history_versions(conn: sqlite3.Connection) -> List[int]:
    rows = conn.execute("SELECT version FROM ScheduleHistory ORDER BY version").fetchall()
    return [int(row["version"]) for row in rows]


def _version_seq_max(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(version), 0) AS version FROM ScheduleVersionSeq").fetchone()
    return int(row["version"] if row else 0)


def test_schedule_history_version_gaps_are_allowed_and_allocated_versions_are_not_reused() -> None:
    conn = _make_connection()
    try:
        repo = ScheduleHistoryRepository(conn, logger=None)
        tx_manager = TransactionManager(conn)

        _create_history(repo, tx_manager, 1)

        allocated_but_not_persisted = _allocate_committed(repo, tx_manager)
        persisted_after_gap = _allocate_committed(repo, tx_manager)
        _create_history(repo, tx_manager, persisted_after_gap)
        next_version = _allocate_committed(repo, tx_manager)

        assert allocated_but_not_persisted == 2
        assert persisted_after_gap == 3
        assert next_version == 4
        assert _history_versions(conn) == [1, 3]
        assert repo.get_by_version(allocated_but_not_persisted) is None
        assert repo.get_latest_version() == 3
        assert [int(row["version"]) for row in repo.list_versions(limit=10)] == [3, 1]
        assert _version_seq_max(conn) == 4
    finally:
        conn.close()


def test_schedule_history_version_allocator_aligns_above_existing_history_max() -> None:
    conn = _make_connection()
    try:
        repo = ScheduleHistoryRepository(conn, logger=None)
        tx_manager = TransactionManager(conn)

        _create_history(repo, tx_manager, 9)

        first_allocated = _allocate_committed(repo, tx_manager)
        second_allocated = _allocate_committed(repo, tx_manager)

        assert repo.get_latest_version() == 9
        assert first_allocated == 10
        assert second_allocated == 11
        assert _history_versions(conn) == [9]
        assert _version_seq_max(conn) == 11
    finally:
        conn.close()
