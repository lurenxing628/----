"""人员设备联动查询与排产版本历史查询。"""

from __future__ import annotations

import sqlite3

import pytest

from core.models.schedule_history import ScheduleHistory
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


def test_schedule_history_row_missing_column_fails_instead_of_defaulting() -> None:
    # 行里缺列说明查询和表结构契约已经对不上，读取时直接报错，不拿默认值顶上。
    row = _mem_conn().execute("SELECT 1 AS id, 2 AS version, 'v2' AS strategy").fetchone()
    with pytest.raises(IndexError):
        ScheduleHistory.from_row(row)
    with pytest.raises(KeyError):
        ScheduleHistory.from_row(dict(row))


def _history_conn_with_versions(*versions) -> sqlite3.Connection:
    conn = _mem_conn()
    conn.execute(
        "CREATE TABLE ScheduleHistory (id INTEGER PRIMARY KEY AUTOINCREMENT, schedule_time TEXT, version INTEGER,"
        " strategy TEXT, batch_count INTEGER, op_count INTEGER, result_status TEXT, result_summary TEXT, created_by TEXT)"
    )
    conn.executemany("INSERT INTO ScheduleHistory(version, strategy) VALUES (?, 's')", [(v,) for v in versions])
    return conn


def _history_row(**values):
    row = {"id": 1, "schedule_time": None, "version": 3, "strategy": "s", "batch_count": None, "op_count": None,
           "result_status": None, "result_summary": None, "created_by": None}
    row.update(values)
    return row


@pytest.mark.parametrize("version", ["", "  ", "abc", 1.5, True, b"\xff1", None])
def test_schedule_history_bad_version_is_corrupt_instead_of_reading_as_one(version) -> None:
    # NOT NULL 的版本号坏了（空、脏文本、非整数、bool、坏字节）是存储损坏，不再读成 1。
    with pytest.raises(ValueError, match="version 必须是整数"):
        ScheduleHistory.from_row(_history_row(version=version))


@pytest.mark.parametrize(("raw", "expected"), [(None, None), ("", None), ("  ", None), (7, 7), (" 7 ", 7), ("7.0", 7)])
def test_schedule_history_optional_counts_read_blank_as_none_and_keep_integer_values(raw, expected) -> None:
    history = ScheduleHistory.from_row(_history_row(batch_count=raw, op_count=raw))
    assert (history.batch_count, history.op_count) == (expected, expected)


@pytest.mark.parametrize("raw", ["x", 1.5, float("nan"), False])
def test_schedule_history_optional_count_with_bad_value_is_corrupt(raw) -> None:
    with pytest.raises(ValueError, match="batch_count 必须是整数"):
        ScheduleHistory.from_row(_history_row(batch_count=raw))


@pytest.mark.parametrize("corrupt", ["abc", b"7"])
def test_latest_version_with_corrupt_stored_value_is_a_query_error(corrupt) -> None:
    # SQLite 允许 INTEGER 列存文本/blob，且 MAX 会返回它；精确整数口径下一律报读取失败，不再把 b"7" 读成 7。
    from core.errors import AppError, ErrorCode

    repo = ScheduleHistoryRepository(_history_conn_with_versions(1, 2, corrupt))
    with pytest.raises(AppError) as caught:
        repo.get_latest_version()
    assert caught.value.code is ErrorCode.DB_QUERY_ERROR
    assert ScheduleHistoryRepository(_history_conn_with_versions(1, 2)).get_latest_version() == 2


@pytest.mark.parametrize(("raw", "expected"), [(None, 8.0), ("", 8.0), ("  ", 8.0), (6, 6.0), (" 7.5 ", 7.5), (b"4", 4.0)])
def test_calendar_row_hours_keep_the_business_default_only_for_missing_values(raw, expected) -> None:
    from core.models.calendar import WorkCalendar

    row = {"date": "2026-05-01", "day_type": "workday", "shift_start": None, "shift_end": None, "shift_hours": raw,
           "efficiency": None, "allow_normal": "yes", "allow_urgent": "yes", "remark": None, "periods_json": None}
    assert (WorkCalendar.from_row(row).shift_hours, WorkCalendar.from_row(row).efficiency) == (expected, 1.0)
    for corrupt in ("abc", float("nan"), True, b"\xff4"):
        with pytest.raises(ValueError, match="shift_hours 必须是数字"):
            WorkCalendar.from_row(dict(row, shift_hours=corrupt))
