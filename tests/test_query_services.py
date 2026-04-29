from __future__ import annotations

import sqlite3

from core.services.equipment.machine_downtime_query_service import MachineDowntimeQueryService
from core.services.personnel.operator_machine_query_service import OperatorMachineQueryService
from core.services.process.part_operation_query_service import PartOperationQueryService
from core.services.scheduler.batch_query_service import BatchQueryService
from core.services.scheduler.schedule_history_query_service import ScheduleHistoryQueryService


def _mem_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    return conn


def test_batch_query_service_has_any() -> None:
    conn = _mem_conn()
    conn.execute("CREATE TABLE Batches (batch_id TEXT PRIMARY KEY)")

    q = BatchQueryService(conn)
    assert q.has_any() is False

    conn.execute("INSERT INTO Batches(batch_id) VALUES (?)", ("B1",))
    assert q.has_any() is True


def test_part_operation_query_service_lists_hours_and_details() -> None:
    conn = _mem_conn()
    conn.execute("CREATE TABLE Parts (part_no TEXT PRIMARY KEY)")
    conn.execute("CREATE TABLE Suppliers (supplier_id TEXT PRIMARY KEY, name TEXT)")
    conn.execute("CREATE TABLE ExternalGroups (group_id TEXT PRIMARY KEY, merge_mode TEXT, total_days REAL)")
    conn.execute(
        """
        CREATE TABLE PartOperations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          part_no TEXT,
          seq INTEGER,
          op_type_name TEXT,
          source TEXT,
          supplier_id TEXT,
          ext_days REAL,
          ext_group_id TEXT,
          setup_hours REAL,
          unit_hours REAL,
          status TEXT
        )
        """
    )

    conn.execute("INSERT INTO Parts(part_no) VALUES (?)", ("P1",))
    conn.execute("INSERT INTO Suppliers(supplier_id, name) VALUES (?, ?)", ("S1", "供应商1"))
    conn.execute("INSERT INTO ExternalGroups(group_id, merge_mode, total_days) VALUES (?, ?, ?)", ("G1", "merged", 12))

    conn.execute(
        """
        INSERT INTO PartOperations
        (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P1", 1, "数铣", "internal", None, None, None, 1.0, 0.5, "active"),
    )
    conn.execute(
        """
        INSERT INTO PartOperations
        (part_no, seq, op_type_name, source, supplier_id, ext_days, ext_group_id, setup_hours, unit_hours, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("P1", 2, "外协", "external", "S1", 3, "G1", 0.0, 0.0, "active"),
    )
    conn.commit()

    q = PartOperationQueryService(conn)

    hours = q.list_active_hours()
    assert len(hours) == 2

    internal_hours = q.list_internal_active_hours()
    assert len(internal_hours) == 1
    assert internal_hours[0]["part_no"] == "P1"
    assert int(internal_hours[0]["seq"] or 0) == 1

    details = q.list_all_active_with_details()
    assert len(details) == 2

    ext = [r for r in details if int(r["seq"] or 0) == 2][0]
    assert ext["supplier_name"] == "供应商1"
    assert ext["merge_mode"] == "merged"
    assert float(ext["total_days"] or 0.0) == 12.0


def test_machine_downtime_query_service_list_active_machine_ids_at() -> None:
    conn = _mem_conn()
    conn.execute(
        """
        CREATE TABLE MachineDowntimes (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          machine_id TEXT,
          start_time TEXT,
          end_time TEXT,
          status TEXT
        )
        """
    )

    q = MachineDowntimeQueryService(conn)
    now = "2026-03-01 10:00:00"

    assert q.list_active_machine_ids_at(now) == set()

    conn.executemany(
        "INSERT INTO MachineDowntimes(machine_id, start_time, end_time, status) VALUES (?, ?, ?, ?)",
        [
            ("M1", "2026-03-01 09:00:00", "2026-03-01 11:00:00", "active"),
            ("M1", "2026-03-01 09:30:00", "2026-03-01 10:30:00", "active"),
            ("M2", "2026-03-01 10:00:00", "2026-03-01 10:00:01", "active"),
            ("M3", "2026-03-01 08:00:00", "2026-03-01 10:00:00", "active"),
            ("M4", "2026-03-01 08:00:00", "2026-03-01 12:00:00", "cancelled"),
            ("   ", "2026-03-01 09:00:00", "2026-03-01 11:00:00", "active"),
            (None, "2026-03-01 09:00:00", "2026-03-01 11:00:00", "active"),
        ],
    )
    conn.commit()

    assert q.list_active_machine_ids_at(now) == {"M1", "M2"}


def test_operator_machine_query_service_lists_with_names_and_linkage_rows() -> None:
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

    q = OperatorMachineQueryService(conn)

    def _by_link_key(rows):
        return {(r.get("operator_id"), r.get("machine_id")): r for r in rows}

    def _assert_normalized_link(row, *, skill_level, is_primary, dirty_skill):
        assert row["skill_level"] == skill_level
        assert row["is_primary"] == is_primary
        if dirty_skill:
            assert row.get("dirty_fields") == ["skill_level"]
            assert "历史技能等级" in row.get("dirty_reasons", {}).get("skill_level", "")
        else:
            assert row.get("dirty_fields", []) == []
            assert row.get("dirty_reasons", {}) == {}

    simple = sorted(q.list_simple_rows(), key=lambda r: (r.get("machine_id"), r.get("operator_id")))
    assert [(r["machine_id"], r["operator_id"]) for r in simple] == [("M1", "O1"), ("M1", "O2"), ("M2", "O1")]
    simple_by_key = _by_link_key(simple)
    _assert_normalized_link(simple_by_key[("O1", "M1")], skill_level="expert", is_primary="yes", dirty_skill=True)
    _assert_normalized_link(simple_by_key[("O2", "M1")], skill_level="normal", is_primary="no", dirty_skill=False)
    _assert_normalized_link(simple_by_key[("O1", "M2")], skill_level="beginner", is_primary="no", dirty_skill=True)

    by_mc = q.list_with_names_by_machine()
    assert [(r["machine_id"], r["operator_id"]) for r in by_mc] == [("M1", "O1"), ("M1", "O2"), ("M2", "O1")]
    assert by_mc[0]["machine_name"] == "机床1"
    assert by_mc[0]["operator_name"] == "张三"
    by_mc_by_key = _by_link_key(by_mc)
    _assert_normalized_link(by_mc_by_key[("O1", "M1")], skill_level="expert", is_primary="yes", dirty_skill=True)
    _assert_normalized_link(by_mc_by_key[("O2", "M1")], skill_level="normal", is_primary="no", dirty_skill=False)
    _assert_normalized_link(by_mc_by_key[("O1", "M2")], skill_level="beginner", is_primary="no", dirty_skill=True)

    by_op = q.list_with_names_by_operator()
    assert [(r["operator_id"], r["machine_id"]) for r in by_op] == [("O1", "M1"), ("O1", "M2"), ("O2", "M1")]
    assert by_op[0]["operator_name"] == "张三"
    assert by_op[0]["machine_name"] == "机床1"
    by_op_by_key = _by_link_key(by_op)
    _assert_normalized_link(by_op_by_key[("O1", "M1")], skill_level="expert", is_primary="yes", dirty_skill=True)
    _assert_normalized_link(by_op_by_key[("O1", "M2")], skill_level="beginner", is_primary="no", dirty_skill=True)
    _assert_normalized_link(by_op_by_key[("O2", "M1")], skill_level="normal", is_primary="no", dirty_skill=False)

    links = q.list_links_with_operator_info()
    assert [(r["machine_id"], r["operator_id"]) for r in links] == [("M1", "O1"), ("M1", "O2"), ("M2", "O1")]
    assert links[0]["operator_name"] == "张三"
    assert links[0]["operator_status"] == "active"
    assert all("dirty_fields" not in r for r in links)
    assert all("dirty_reasons" not in r for r in links)

    sub = q.list_simple_rows_for_machine_operator_sets(["M1", "M2"], ["O1"])
    assert [(r["machine_id"], r["operator_id"]) for r in sub] == [("M1", "O1"), ("M2", "O1")]
    sub_by_key = _by_link_key(sub)
    _assert_normalized_link(sub_by_key[("O1", "M1")], skill_level="expert", is_primary="yes", dirty_skill=True)
    _assert_normalized_link(sub_by_key[("O1", "M2")], skill_level="beginner", is_primary="no", dirty_skill=True)
    sub_normal = q.list_simple_rows_for_machine_operator_sets(["M1"], ["O2"])
    assert [(r["machine_id"], r["operator_id"]) for r in sub_normal] == [("M1", "O2")]
    _assert_normalized_link(sub_normal[0], skill_level="normal", is_primary="no", dirty_skill=False)
    assert q.list_simple_rows_for_machine_operator_sets([], ["O1"]) == []
    assert q.list_simple_rows_for_machine_operator_sets(["M1"], []) == []


def test_operator_machine_query_service_marks_dirty_primary_blank() -> None:
    row = OperatorMachineQueryService._normalize_row(
        {"operator_id": "O1", "machine_id": "M1", "skill_level": "normal", "is_primary": ""}
    )

    assert row["skill_level"] == "normal"
    assert row["is_primary"] == "no"
    assert "is_primary" in row.get("dirty_fields", [])
    assert "历史主操标记为空" in row.get("dirty_reasons", {}).get("is_primary", "")


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
            ("2026-03-03 10:00:00", 2, "v2", 12, 102, "ok2", "{}", "u3"),
        ],
    )
    conn.commit()

    q = ScheduleHistoryQueryService(conn)

    assert q.get_latest_version() == 2

    h1 = q.get_by_version(1)
    assert h1 is not None
    assert h1.version == 1
    assert h1.strategy == "s_new"
    assert h1.result_status == "fail"

    versions = q.list_versions(limit=10)
    assert [int(r["version"] or 0) for r in versions] == [2, 1]
    v1 = [r for r in versions if int(r["version"] or 0) == 1][0]
    assert v1["strategy"] == "s_new"
    assert v1["result_status"] == "fail"
    assert v1["schedule_time"] == "2026-03-02 10:00:00"

    recent = q.list_recent(limit=2)
    assert len(recent) == 2
    assert int(recent[0].version or 0) == 2
    assert int(recent[1].version or 0) == 1
