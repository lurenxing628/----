from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

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

DISPATCH_DETAIL_KEYS = COMMON_DETAIL_KEYS | {
    "machine_team_id",
    "machine_team_name",
    "operator_team_id",
    "operator_team_name",
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
            ('B4', 'P004', '零件四', '2026-05-04', 'normal');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source, status, supplier_id
        )
        VALUES
            (10, 'OP10', 'B1', 'piece-a', 1, '车削', 'internal', 'scheduled', 'S1'),
            (11, 'OP11', 'B2', 'piece-b', 2, '磨削', 'internal', 'scheduled', NULL),
            (12, 'OP12', 'B3', 'piece-c', 3, '装配', 'internal', 'scheduled', NULL),
            (13, 'OP13', 'B4', 'piece-d', 4, '外协', 'external', 'scheduled', 'S2');

        INSERT INTO Schedule(
            id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version
        )
        VALUES
            (1, 10, 'M1', 'O1', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 1),
            (2, 11, 'M2', 'O2', '2026-05-01 07:00', '2026-05-01 09:00', 'unlocked', 1),
            (3, 12, 'M1', 'O2', '2026-05-01 10:00', '2026-05-01 11:00', 'unlocked', 1),
            (4, 13, NULL, NULL, '2026-05-01 09:30', '2026-05-01 10:30', 'unlocked', 1),
            (5, 10, 'M1', 'O1', '2026-05-01 08:00', '2026-05-01 10:00', 'unlocked', 2);
        """
    )


def _repo() -> ScheduleRepository:
    conn = _conn()
    _seed(conn)
    return ScheduleRepository(conn)


def _ids(rows: List[Dict[str, Any]]) -> List[int]:
    return [int(row["schedule_id"]) for row in rows]


def test_schedule_overlap_detail_query_keeps_row_shape_order_and_overlap_contract() -> None:
    repo = _repo()

    rows = repo.list_overlapping_with_details(
        start_time="2026-05-01 08:30",
        end_time="2026-05-01 10:00",
        version=1,
    )

    assert _ids(rows) == [2, 1, 4]
    assert set(rows[0]) == COMMON_DETAIL_KEYS
    assert all("machine_team_id" not in row for row in rows)
    assert all("operator_team_id" not in row for row in rows)

    external = rows[2]
    assert external["machine_id"] is None
    assert external["operator_id"] is None
    assert external["supplier_name"] == "外协供应商"


def test_schedule_detail_query_for_version_uses_same_common_shape() -> None:
    repo = _repo()

    rows = repo.list_by_version_with_details(version=1)

    assert _ids(rows) == [2, 1, 4, 3]
    assert set(rows[0]) == COMMON_DETAIL_KEYS
    assert all("machine_team_id" not in row for row in rows)


def test_schedule_dispatch_query_includes_team_context_and_operator_scope() -> None:
    repo = _repo()

    rows = repo.list_dispatch_rows_with_resource_context(
        start_time="2026-05-01 00:00",
        end_time="2026-05-02 00:00",
        version=1,
        scope_type="operator",
        scope_id="O1",
    )

    assert _ids(rows) == [1]
    row = rows[0]
    assert set(row) == DISPATCH_DETAIL_KEYS
    assert row["machine_team_id"] == "T-M"
    assert row["machine_team_name"] == "设备班组"
    assert row["operator_team_id"] == "T-O"
    assert row["operator_team_name"] == "人员班组"


def test_schedule_dispatch_query_keeps_machine_and_team_scope_filters() -> None:
    repo = _repo()

    machine_rows = repo.list_dispatch_rows_with_resource_context(
        start_time="2026-05-01 00:00",
        end_time="2026-05-02 00:00",
        version=1,
        scope_type="machine",
        scope_id="M2",
    )
    team_rows = repo.list_dispatch_rows_with_resource_context(
        start_time="2026-05-01 00:00",
        end_time="2026-05-02 00:00",
        version=1,
        scope_type="team",
        scope_id="T-2",
    )

    assert _ids(machine_rows) == [2]
    assert _ids(team_rows) == [2, 3]


def test_schedule_dispatch_query_keeps_left_join_for_unassigned_external_rows() -> None:
    repo = _repo()

    rows = repo.list_dispatch_rows_with_resource_context(
        start_time="2026-05-01 08:30",
        end_time="2026-05-01 10:00",
        version=1,
    )

    assert _ids(rows) == [2, 1, 4]
    external = rows[2]
    assert external["machine_name"] is None
    assert external["operator_name"] is None
    assert external["supplier_name"] == "外协供应商"
