"""回归测试：报表计算对 source 大小写不敏感，坏时间不能在查询链路里静默丢失。"""

import sqlite3
from datetime import datetime
from types import SimpleNamespace


def test_report_source_case_insensitive() -> None:

    from core.services.report.calculations import compute_downtime_impact, compute_utilization

    upper_row = {
        "source": "INTERNAL",
        "machine_id": "M1",
        "machine_name": "机1",
        "operator_id": "O1",
        "operator_name": "人1",
        "start_time": "2026-01-01 08:00:00",
        "end_time": "2026-01-01 10:00:00",
    }
    lower_row = dict(upper_row, source="internal")
    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    end_dt_excl = datetime(2026, 1, 2, 0, 0, 0)

    upper_machine, upper_operator = compute_utilization(
        schedule_rows=[upper_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
    )
    lower_machine, lower_operator = compute_utilization(
        schedule_rows=[lower_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
    )
    assert upper_machine == lower_machine, "compute_utilization 应对 source 大小写不敏感（machine）"
    assert upper_operator == lower_operator, "compute_utilization 应对 source 大小写不敏感（operator）"

    downtime_rows = [
        {
            "machine_id": "M1",
            "machine_name": "机1",
            "start_time": "2026-01-01 09:00:00",
            "end_time": "2026-01-01 11:00:00",
            "reason_code": "maint",
            "reason_detail": "保养",
        }
    ]
    upper_downtime = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=[upper_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )
    lower_downtime = compute_downtime_impact(
        downtime_rows=downtime_rows,
        schedule_rows=[lower_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
    )
    assert upper_downtime == lower_downtime, "compute_downtime_impact 应对 source 大小写不敏感"


def test_report_calculations_record_bad_time_degradation() -> None:
    from core.services.common.degradation import DegradationCollector
    from core.services.report.calculations import compute_downtime_impact, compute_utilization

    start_dt = datetime(2026, 1, 1, 0, 0, 0)
    end_dt_excl = datetime(2026, 1, 2, 0, 0, 0)
    good_row = {
        "source": "internal",
        "machine_id": "M1",
        "machine_name": "机1",
        "operator_id": "O1",
        "operator_name": "人1",
        "start_time": "2026-01-01 08:00:00",
        "end_time": "2026-01-01 10:00:00",
    }
    bad_schedule_row = dict(good_row, start_time="2026-01-01 99:00:00", end_time="2026-01-01 11:00:00")

    util_collector = DegradationCollector()
    machine_rows, operator_rows = compute_utilization(
        schedule_rows=[good_row, bad_schedule_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        cap_hours=24.0,
        degradation_collector=util_collector,
    )

    assert machine_rows[0]["task_count"] == 1
    assert operator_rows[0]["task_count"] == 1
    assert util_collector.to_counters()["bad_time_row_skipped"] == 1
    assert "99:00:00" not in str(util_collector.to_list())

    downtime_collector = DegradationCollector()
    downtime_rows = compute_downtime_impact(
        downtime_rows=[
            {
                "machine_id": "M1",
                "machine_name": "机1",
                "start_time": "2026-01-01 09:00:00",
                "end_time": "2026-01-01 11:00:00",
                "reason_code": "maint",
                "reason_detail": "保养",
            },
            {
                "machine_id": "M1",
                "machine_name": "机1",
                "start_time": "2026-01-01 99:00:00",
                "end_time": "2026-01-01 12:00:00",
                "reason_code": "maint",
                "reason_detail": "坏时间停机",
            },
        ],
        schedule_rows=[good_row, bad_schedule_row],
        start_dt=start_dt,
        end_dt_excl=end_dt_excl,
        degradation_collector=downtime_collector,
    )

    assert downtime_rows[0]["downtime_count"] == 1
    assert downtime_collector.to_counters()["bad_time_row_skipped"] == 2
    assert "99:00:00" not in str(downtime_collector.to_list())


def test_downtime_batch_filter_records_bad_time_rows_before_filtering() -> None:
    from core.services.common.degradation import DegradationCollector
    from core.services.report.report_context_filters import filter_downtime_rows_for_report_context

    collector = DegradationCollector()
    schedule_rows = [
        {
            "batch_id": "B1",
            "source": "internal",
            "machine_id": "M1",
            "start_time": "2026-01-01 08:00:00",
            "end_time": "2026-01-01 10:00:00",
        }
    ]
    downtime_rows = [
        {
            "machine_id": "M1",
            "machine_name": "机1",
            "start_time": "2026-01-01 99:00:00",
            "end_time": "2026-01-01 12:00:00",
        }
    ]

    filtered = filter_downtime_rows_for_report_context(
        downtime_rows,
        schedule_rows,
        batch_id="B1",
        degradation_collector=collector,
    )

    assert filtered == []
    assert collector.to_counters()["bad_time_row_skipped"] == 1
    assert "99:00:00" not in str(collector.to_list())


def _report_engine_test_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE ScheduleHistory(
            id INTEGER PRIMARY KEY,
            version INTEGER,
            schedule_time TEXT,
            result_status TEXT,
            result_summary TEXT
        );
        CREATE TABLE ScheduleCandidateSelection(
            version INTEGER,
            role TEXT,
            candidate_id INTEGER,
            source_table TEXT
        );
        CREATE TABLE ScheduleCandidate(
            id INTEGER PRIMARY KEY,
            version INTEGER,
            candidate_key TEXT,
            candidate_label TEXT,
            candidate_kind TEXT,
            status TEXT,
            detail_saved INTEGER
        );
        CREATE TABLE ScheduleCandidateRows(
            id INTEGER PRIMARY KEY,
            version INTEGER,
            candidate_id INTEGER,
            op_id INTEGER,
            machine_id TEXT,
            operator_id TEXT,
            start_time TEXT,
            end_time TEXT,
            lock_status TEXT
        );
        CREATE TABLE BatchOperations(
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
        CREATE TABLE Batches(
            batch_id TEXT PRIMARY KEY,
            part_no TEXT,
            part_name TEXT,
            due_date TEXT,
            priority TEXT
        );
        CREATE TABLE Machines(machine_id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE Operators(operator_id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE Suppliers(supplier_id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE Schedule(
            id INTEGER PRIMARY KEY,
            op_id INTEGER,
            machine_id TEXT,
            operator_id TEXT,
            start_time TEXT,
            end_time TEXT,
            lock_status TEXT,
            version INTEGER
        );
        CREATE TABLE MachineDowntimes(
            id INTEGER PRIMARY KEY,
            machine_id TEXT,
            scope_type TEXT,
            scope_value TEXT,
            start_time TEXT,
            end_time TEXT,
            reason_code TEXT,
            reason_detail TEXT,
            status TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        """
    )
    conn.execute(
        "INSERT INTO ScheduleHistory(version, schedule_time, result_status, result_summary) VALUES (1, '2026-01-01 12:00:00', 'success', '{}')"
    )
    conn.execute("INSERT INTO Batches(batch_id, part_no, part_name, due_date, priority) VALUES ('B1', 'P1', '零件一', '2026-01-03', 'normal')")
    conn.execute("INSERT INTO Machines(machine_id, name) VALUES ('M1', '设备一')")
    conn.execute("INSERT INTO Operators(operator_id, name) VALUES ('O1', '人员一')")
    conn.executemany(
        """
        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status, supplier_id)
        VALUES (?, ?, 'B1', 'P1', ?, '加工', 'internal', 'pending', NULL)
        """,
        [(1, "OP1", 1), (2, "OP2", 2)],
    )
    conn.executemany(
        """
        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (?, ?, 'M1', 'O1', ?, ?, 'scheduled', 1)
        """,
        [
            (1, 1, "2026-01-01 08:00:00", "2026-01-01 10:00:00"),
            (2, 2, "坏值", "2026-01-01 11:00:00"),
        ],
    )
    conn.executemany(
        """
        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, reason_code, reason_detail, status)
        VALUES ('M1', ?, ?, 'maint', ?, 'active')
        """,
        [
            ("2026-01-01 09:00:00", "2026-01-01 11:00:00", "保养"),
            ("坏值", "2026-01-01 12:00:00", "坏时间停机"),
        ],
    )
    conn.commit()
    return conn


def test_report_engine_records_bad_time_rows_that_sql_range_cannot_classify() -> None:
    from core.services.report.report_engine import ReportEngine

    conn = _report_engine_test_conn()
    engine = ReportEngine(conn)
    engine.calendar = SimpleNamespace(policy_for_datetime=lambda _dt: SimpleNamespace(shift_hours=8.0, efficiency=1.0))

    utilization = engine.utilization(1, "2026-01-01", "2026-01-01")
    downtime = engine.downtime_impact(1, "2026-01-01", "2026-01-01")

    assert utilization["machines"][0]["task_count"] == 1
    assert utilization["report_bad_time_skipped_count"] == 1
    assert "已过滤 1 条" in utilization["report_degradation_message"]
    assert downtime["machines"][0]["downtime_count"] == 1
    assert downtime["report_bad_time_skipped_count"] == 2
    assert "坏值" not in str(utilization.get("report_degradation_events"))
    assert "坏值" not in str(downtime.get("report_degradation_events"))
