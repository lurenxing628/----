"""回归测试：MachineDowntimeRepository.list_active_after(machine_id, start) 只返回指定机台、status='active'、且 end_time 晚于 start 的停机段（含跨 start 的段），排除已取消和其他机台，并按 start_time 升序返回。"""

from __future__ import annotations

import sqlite3

import pytest

from data.repositories.machine_downtime_repo import MachineDowntimeRepository


def test_list_active_after_returns_only_active_rows_ending_after_start_ordered() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    rows = [
        ("MC_1", "2026-01-01 07:30:00", "2026-01-01 08:30:00", "active"),
        ("MC_1", "2026-01-01 12:00:00", "2026-01-01 13:00:00", "active"),
        ("MC_1", "2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
        ("MC_1", "2026-01-01 07:00:00", "2026-01-01 08:00:00", "active"),
        ("MC_1", "2026-01-01 14:00:00", "2026-01-01 15:00:00", "cancelled"),
        ("MC_2", "2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
    ]
    conn.executemany(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )

    try:
        found = MachineDowntimeRepository(conn).list_active_after("MC_1", "2026-01-01 08:00:00")
    finally:
        conn.close()

    assert [(item.start_time, item.end_time, item.status) for item in found] == [
        ("2026-01-01 07:30:00", "2026-01-01 08:30:00", "active"),
        ("2026-01-01 09:00:00", "2026-01-01 10:00:00", "active"),
        ("2026-01-01 12:00:00", "2026-01-01 13:00:00", "active"),
    ]


def test_active_overlap_query_parses_window_params_with_same_python_contract() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE Machines (
            machine_id TEXT PRIMARY KEY,
            name TEXT
        );
        """
    )
    conn.execute("INSERT INTO Machines(machine_id, name) VALUES ('MC_1', '一号机')")
    conn.execute(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, reason_code, status)
        VALUES ('MC_1', '2026/02/14 08:30:00', '2026/02/14 09:30:00', 'maintenance', 'active')
        """
    )

    try:
        found = MachineDowntimeRepository(conn).list_active_overlaps_with_machine_names(
            "2026/02/14 08:00:00",
            "2026/02/14 10:00:00",
        )
    finally:
        conn.close()

    assert [(row["machine_id"], row["machine_name"]) for row in found] == [("MC_1", "一号机")]


def test_active_overlap_query_rejects_invalid_window_params() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE Machines (
            machine_id TEXT PRIMARY KEY,
            name TEXT
        );
        """
    )

    try:
        repo = MachineDowntimeRepository(conn)
        with pytest.raises(ValueError, match="停机重叠查询时间写法不对"):
            repo.list_active_overlaps_with_machine_names("not-a-time", "2026-02-14 10:00:00")
        with pytest.raises(ValueError, match="停机重叠查询时间写法不对"):
            repo.list_active_overlaps_with_machine_names("2026-02-14 08:00:00", "not-a-time")
    finally:
        conn.close()


def test_has_overlap_and_active_machine_ids_parse_times_with_same_python_contract() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.execute(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES ('MC_1', '2026/02/14 08:30:00', '2026/02/14 09:30:00', 'active')
        """
    )

    try:
        repo = MachineDowntimeRepository(conn)

        assert repo.has_overlap("MC_1", "2026-02-14T08:00:00", "2026-02-14T09:00:00") is True
        assert repo.list_active_machine_ids_at("2026-02-14T08:45:00") == {"MC_1"}
        with pytest.raises(ValueError, match="停机重叠检查开始时间写法不对"):
            repo.has_overlap("MC_1", "not-a-time", "2026-02-14 09:00:00")
        with pytest.raises(ValueError, match="停机重叠检查结束时间写法不对"):
            repo.has_overlap("MC_1", "2026-02-14 08:00:00", "not-a-time")
        with pytest.raises(ValueError, match="停机状态查询时间写法不对"):
            repo.list_active_machine_ids_at("not-a-time")
    finally:
        conn.close()


def test_list_active_after_parses_start_param_with_same_python_contract() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn.executemany(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES (?, ?, ?, ?)
        """,
        [
            ("MC_1", "2026-02-14 08:00:00", "2026-02-14 09:00:00", "active"),
            ("MC_1", "2026-02-14 07:00:00", "2026-02-14 08:00:00", "active"),
        ],
    )

    try:
        found = MachineDowntimeRepository(conn).list_active_after("MC_1", "2026/02/14 08:30:00")
    finally:
        conn.close()

    assert [(item.start_time, item.end_time) for item in found] == [
        ("2026-02-14 08:00:00", "2026-02-14 09:00:00")
    ]


def test_list_active_after_rejects_invalid_start_param() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    try:
        with pytest.raises(ValueError, match="停机查询开始时间写法不对"):
            MachineDowntimeRepository(conn).list_active_after("MC_1", "not-a-time")
    finally:
        conn.close()


def test_decision_queries_exclude_bad_time_rows_no_fallback() -> None:
    """契约：判定类查询（重叠/可用性/排产占用）有意把坏时间停机行排除，不做坏行兜底。

    与 list_active_overlaps_with_machine_names（明细展示，兜底坏行做降级提示）口径相反——
    判定类把坏行当“冲突/不可用/占用”会对任意窗口误报封锁，比坏行静默消失更糟。
    本测试钉住该 by-design 分工，防止有人“好心”给三处加 overlap_or_bad_time_sql 兜底。
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE MachineDowntimes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            machine_id TEXT NOT NULL,
            scope_type TEXT DEFAULT 'machine',
            scope_value TEXT,
            start_time DATETIME NOT NULL,
            end_time DATETIME NOT NULL,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT DEFAULT 'active',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    # 一条坏时间的 active 停机行（end_time 无法解析）
    conn.execute(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status)
        VALUES ('MC_1', '2026-02-14 08:00:00', 'not-a-time', 'active')
        """
    )

    try:
        repo = MachineDowntimeRepository(conn)
        # 重叠判定：坏行不被当作冲突，新停机可正常创建（不误报封锁）
        assert repo.has_overlap("MC_1", "2026-02-14 08:30:00", "2026-02-14 09:30:00") is False
        # 可用性判定：坏行设备不被永久标记为停机不可用
        assert repo.list_active_machine_ids_at("2026-02-14 08:30:00") == set()
        # 排产占用：坏行不进占用区间
        assert repo.list_active_after("MC_1", "2026-02-14 00:00:00") == []
    finally:
        conn.close()
