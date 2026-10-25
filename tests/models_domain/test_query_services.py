"""人员设备联动查询与排产版本历史查询。"""

from __future__ import annotations

import sqlite3

from core.services.personnel.operator_machine_normalizers import normalize_operator_machine_row
from core.services.workbench.resource.projection import _authorization_issues
from data.repositories import OperatorMachineRepository, ScheduleHistoryRepository


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def _operator_machine_repository() -> OperatorMachineRepository:
    conn = _mem_conn()
    conn.execute("CREATE TABLE Machines (machine_id TEXT PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE Operators (operator_id TEXT PRIMARY KEY, name TEXT, status TEXT)")
    conn.execute(
        """
        CREATE TABLE OperatorMachine (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          operator_id TEXT,
          machine_id TEXT,
          skill_level TEXT,
          is_primary TEXT
        )
        """
    )

    conn.executemany("INSERT INTO Machines(machine_id, name) VALUES (?, ?)", [("M1", "机床1"), ("M2", "机床2")])
    conn.executemany(
        "INSERT INTO Operators(operator_id, name, status) VALUES (?, ?, ?)",
        [("O1", "张三", "active"), ("O2", "李四", "inactive")],
    )
    conn.executemany(
        "INSERT INTO OperatorMachine(operator_id, machine_id, skill_level, is_primary) VALUES (?, ?, ?, ?)",
        [
            ("O1", "M1", "high", "yes"),
            ("O2", "M1", "normal", "no"),
            ("O1", "M2", "low", "no"),
        ],
    )
    conn.commit()
    return OperatorMachineRepository(conn)


def _operator_machine_rows_by_key(rows):
    return {(r["operator_id"], r["machine_id"]): r for r in rows}


def _assert_operator_machine_link(row, *, skill_level, is_primary, dirty_skill):
    assert row["skill_level"] == skill_level
    assert row["is_primary"] == is_primary
    if dirty_skill:
        assert row.get("dirty_fields") == ["skill_level"]
    else:
        assert row.get("dirty_fields", []) == []


def test_operator_machine_normalizer_lists_with_names_and_linkage_rows() -> None:
    repo = _operator_machine_repository()
    raw_rows = repo.list_simple_rows_for_operators(["O1", "O2"])
    by_operator = [normalize_operator_machine_row(row) for row in raw_rows]
    assert [(row["operator_id"], row["machine_id"]) for row in by_operator] == [
        ("O1", "M1"), ("O1", "M2"), ("O2", "M1"),
    ]
    rows = _operator_machine_rows_by_key(by_operator)
    _assert_operator_machine_link(rows[("O1", "M1")], skill_level="expert", is_primary="yes", dirty_skill=True)
    _assert_operator_machine_link(rows[("O1", "M2")], skill_level="beginner", is_primary="no", dirty_skill=True)
    _assert_operator_machine_link(rows[("O2", "M1")], skill_level="normal", is_primary="no", dirty_skill=False)
    assert _authorization_issues(raw_rows) == [
        {
            "code": "machine_authorization_dirty",
            "fields": ["skill_level"],
            "message": "设备“M1”的授权记录要核对，涉及：技能等级。系统只是按兼容规则解释，原值没有被改。",
        },
        {
            "code": "machine_authorization_dirty",
            "fields": ["skill_level"],
            "message": "设备“M2”的授权记录要核对，涉及：技能等级。系统只是按兼容规则解释，原值没有被改。",
        },
    ]



def test_schedule_history_query_service_versions_and_latest() -> None:
    conn = _mem_conn()
    conn.execute(
        """
        CREATE TABLE ScheduleHistory (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          schedule_time TEXT,
          version INTEGER,
          strategy TEXT,
          batch_count INTEGER,
          op_count INTEGER,
          result_status TEXT,
          result_summary TEXT,
          created_by TEXT
        )
        """
    )
    conn.executemany(
        """
        INSERT INTO ScheduleHistory
        (schedule_time, version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            ("2026-03-01 10:00:00", 1, "s_old", 10, 100, "ok", "{}", "u1"),
            ("2026-03-02 10:00:00", 1, "s_new", 11, 101, "fail", "{}", "u2"),
            ("2026-03-03 10:00:00", 2, "v2", 12, 102, "simulated", "{}", "u3"),
        ],
    )
    conn.commit()

    q = ScheduleHistoryRepository(conn)

    assert q.get_latest_version() == 2

    h1 = q.get_by_version(1)
    assert h1 is not None
    assert h1.version == 1
    assert h1.strategy == "s_new"
    assert h1.result_status == "fail"
