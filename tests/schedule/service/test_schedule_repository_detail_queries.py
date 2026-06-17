"""回归测试：ScheduleRepository 明细查询契约——list_by_version_with_details 返回固定的 COMMON_DETAIL_KEYS 行形状、按版本过滤、外协行 machine/operator 为 None 而 supplier_name 仍解析。"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

import pytest

from data.repositories.schedule_repo import ScheduleRepository

COMMON_DETAIL_KEYS = {
    "schedule_id",
    "op_id",
    "start_time",
    "end_time",
    "lock_status",
    "version",
    "op_code",
    "batch_id",
    "piece_id",
    "seq",
    "op_type_name",
    "source",
    "op_status",
    "machine_id",
    "operator_id",
    "supplier_id",
    "part_no",
    "part_name",
    "due_date",
    "priority",
    "machine_name",
    "operator_name",
    "supplier_name",
}


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE Schedule (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            op_id INTEGER,
            machine_id TEXT,
            operator_id TEXT,
            start_time TEXT,
            end_time TEXT,
            lock_status TEXT,
            version INTEGER,
            created_at TEXT
        );

        CREATE TABLE BatchOperations (
            id INTEGER PRIMARY KEY,
            op_code TEXT,
            batch_id TEXT,
            piece_id TEXT,
            seq INTEGER,
            op_type_name TEXT,
            source TEXT,
            status TEXT,
            supplier_id TEXT
        );

        CREATE TABLE Batches (
            batch_id TEXT PRIMARY KEY,
            part_no TEXT,
            part_name TEXT,
            due_date TEXT,
            priority TEXT
        );

        CREATE TABLE Machines (
            machine_id TEXT PRIMARY KEY,
            name TEXT,
            team_id TEXT
        );

        CREATE TABLE Operators (
            operator_id TEXT PRIMARY KEY,
            name TEXT,
            team_id TEXT
        );

        CREATE TABLE ResourceTeams (
            team_id TEXT PRIMARY KEY,
            name TEXT
        );

        CREATE TABLE Suppliers (
            supplier_id TEXT PRIMARY KEY,
            name TEXT
        );
        """
    )
    return conn


def _seed(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name)
        VALUES ('T-M', '设备班组'), ('T-O', '人员班组'), ('T-2', '第二班组');

        INSERT INTO Machines(machine_id, name, team_id)
        VALUES ('M1', '设备一', 'T-M'), ('M2', '设备二', 'T-2');

        INSERT INTO Operators(operator_id, name, team_id)
        VALUES ('O1', '人员一', 'T-O'), ('O2', '人员二', 'T-2');

        INSERT INTO Suppliers(supplier_id, name)
        VALUES ('S1', '供应商一'), ('S2', '外协供应商');

        INSERT INTO Batches(batch_id, part_no, part_name, due_date, priority)
        VALUES
            ('B1', 'P001', '零件一', '2026-05-01', 'urgent'),
            ('B2', 'P002', '零件二', '2026-05-02', 'normal'),
            ('B3', 'P003', '零件三', '2026-05-03', 'low'),
            ('B4', 'P004', '零件四', '2026-05-04', 'normal'),
            ('B5', 'P005', '零件五', '2026-05-05', 'normal'),
            ('B6', 'P006', '零件六', '2026-05-06', 'normal');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source, status, supplier_id
        )
        VALUES
            (10, 'OP10', 'B1', 'piece-a', 1, '车削', 'internal', 'scheduled', 'S1'),
            (11, 'OP11', 'B2', 'piece-b', 2, '磨削', 'internal', 'scheduled', NULL),
            (12, 'OP12', 'B3', 'piece-c', 3, '装配', 'internal', 'scheduled', NULL),
            (13, 'OP13', 'B4', 'piece-d', 4, '外协', 'external', 'scheduled', 'S2'),
            (14, 'OP14', 'B5', 'piece-e', 5, '人工检验', 'internal', 'scheduled', NULL),
            (15, 'OP15', 'B6', 'piece-f', 6, '设备试切', 'internal', 'scheduled', NULL);

        INSERT INTO Schedule(
            id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        )
        VALUES
            (1, 10, 'M1', 'O1', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 1),
            (2, 11, 'M2', 'O2', '2026-05-01 07:00', '2026-05-01 09:00', 'unlocked', 1),
            (3, 12, 'M1', 'O2', '2026-05-01 10:00', '2026-05-01 11:00', 'unlocked', 1),
            (4, 13, NULL, NULL, '2026-05-01 09:30', '2026-05-01 10:30', 'unlocked', 1),
            (6, 14, NULL, 'O1', '2026-05-01 08:45', '2026-05-01 09:15', 'unlocked', 3),
            (7, 15, 'M2', NULL, '2026-05-01 08:50', '2026-05-01 09:20', 'unlocked', 3),
            (5, 10, 'M1', 'O1', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 2);
        """
    )


def _repo() -> ScheduleRepository:
    conn = _conn()
    _seed(conn)
    return ScheduleRepository(conn)


def _ids(rows: List[Dict[str, Any]]) -> List[int]:
    return [int(row["schedule_id"]) for row in rows]


def test_seed_range_query_uses_python_time_parser_for_existing_rows() -> None:
    repo = _repo()
    repo.conn.execute(
        "UPDATE Schedule SET start_time = ?, end_time = ? WHERE id = ?",
        ("2026/05/01 08:00", "2026/05/01 10:00", 1),
    )

    rows = repo.list_version_rows_by_op_ids_start_range(
        version=1,
        op_ids=[10],
        start_time="2026-05-01 09:00",
        end_time="2026-05-01 09:30",
    )

    assert [int(row["op_id"]) for row in rows] == [10]


def test_seed_range_query_rejects_invalid_window_boundary() -> None:
    repo = _repo()

    with pytest.raises(ValueError, match="冻结窗口查询时间写法不对"):
        repo.list_version_rows_by_op_ids_start_range(
            version=1,
            op_ids=[10],
            start_time="bad-start",
            end_time="2026-05-01 09:30",
        )


def test_schedule_detail_query_for_version_uses_same_common_shape() -> None:
    repo = _repo()

    rows = repo.list_by_version_with_details(version=1)

    assert _ids(rows) == [2, 1, 4, 3]
    assert set(rows[0]) == COMMON_DETAIL_KEYS
    assert all("machine_team_id" not in row for row in rows)
