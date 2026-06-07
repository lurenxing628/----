"""回归测试：仓库层禁止把读取失败静默兜底成"零"——ConfigRepository.count_all 和 ScheduleHistoryRepository.get_latest_version 遇到不可解析的标量（非整数/空/负/小数）须抛 AppError 而非返回 0，真空历史才返回 0，且 ExternalGroupRepository.update 命中 0 行须抛 BusinessError 提示不存在。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from core.infrastructure.errors import AppError, BusinessError
from data.repositories.config_repo import ConfigRepository
from data.repositories.external_group_repo import ExternalGroupRepository
from data.repositories.schedule_history_repo import ScheduleHistoryRepository
from tests._support.paths import REPO_ROOT


def _make_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript((REPO_ROOT / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    return conn


class _BadScalarRepo(ConfigRepository):
    def __init__(self, value):
        self.value = value

    def fetchvalue(self, *_args, **_kwargs):
        return self.value


class _BadLatestVersionRepo(ScheduleHistoryRepository):
    def __init__(self, value):
        self.value = value

    def fetchvalue(self, *_args, **_kwargs):
        return self.value


@pytest.mark.parametrize("value", ["not-a-count", "", None, False, -1, 0.5, 1.5])
def test_config_count_all_rejects_unreadable_count_instead_of_pristine_zero(value) -> None:
    with pytest.raises(AppError) as exc_info:
        _BadScalarRepo(value).count_all()

    assert "读取排产配置数量失败" in exc_info.value.message


@pytest.mark.parametrize("value", ["bad-version", "", None, False, -1, 0.5, 1.5])
def test_schedule_history_latest_version_rejects_unreadable_value_instead_of_no_history(value) -> None:
    with pytest.raises(AppError) as exc_info:
        _BadLatestVersionRepo(value).get_latest_version()

    assert "读取最新排产版本失败" in exc_info.value.message


def test_schedule_history_latest_version_keeps_empty_history_as_zero() -> None:
    conn = _make_connection()
    try:
        assert ScheduleHistoryRepository(conn).get_latest_version() == 0
    finally:
        conn.close()


def test_schedule_history_latest_version_rejects_real_sqlite_version_instead_of_truncating() -> None:
    conn = _make_connection()
    try:
        conn.execute(
            "INSERT INTO ScheduleHistory (version, strategy, batch_count, op_count, result_status, result_summary, created_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (1.5, "priority_first", 0, 0, "success", "{}", "pytest"),
        )
        conn.commit()

        with pytest.raises(AppError) as exc_info:
            ScheduleHistoryRepository(conn).get_latest_version()

        assert "读取最新排产版本失败" in exc_info.value.message
    finally:
        conn.close()


def test_external_group_update_rejects_zero_row_update() -> None:
    conn = _make_connection()
    try:
        repo = ExternalGroupRepository(conn)

        with pytest.raises(BusinessError) as exc_info:
            repo.update("missing-group", {"merge_mode": "merged"})

        assert "不存在或已被删除" in exc_info.value.message
    finally:
        conn.close()
