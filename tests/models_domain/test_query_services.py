"""人员设备联动查询与工作日历行解析。"""

from __future__ import annotations

import sqlite3

import pytest

from core.services.personnel.operator_machine_normalizers import normalize_operator_machine_row
from core.services.workbench.resource.projection import _authorization_issues
from data.repositories import OperatorMachineRepository


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


@pytest.mark.parametrize(("raw", "expected"), [(None, 8.0), ("", 8.0), ("  ", 8.0), (6, 6.0), (" 7.5 ", 7.5), (b"4", 4.0)])
def test_calendar_row_hours_keep_the_business_default_only_for_missing_values(raw, expected) -> None:
    from core.models.calendar import WorkCalendar

    row = {"date": "2026-05-01", "day_type": "workday", "shift_start": None, "shift_end": None, "shift_hours": raw,
           "efficiency": None, "allow_normal": "yes", "allow_urgent": "yes", "remark": None, "periods_json": None}
    assert (WorkCalendar.from_row(row).shift_hours, WorkCalendar.from_row(row).efficiency) == (expected, 1.0)
    for corrupt in ("abc", float("nan"), True, b"\xff4"):
        with pytest.raises(ValueError, match="shift_hours 必须是数字"):
            WorkCalendar.from_row(dict(row, shift_hours=corrupt))
