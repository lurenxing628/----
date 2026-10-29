"""Overdue calculations preserve source identity and invalid-time buckets."""

from __future__ import annotations

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    SOURCE_SCHEDULE,
)
from core.services.common.plan_query import SchedulePlanQueryService
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 11
AS_OF_TIME = "2026-05-05 12:00:00"


def _connect(tmp_path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH))
    return get_connection(str(db_path))


def _table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _snapshot(conn):
    tables = [
        "Schedule",
        "ScheduleHistory",
        "ScheduleVersionSeq",
        "Materials",
        "Batches",
        "BatchMaterials",
        "MachineDowntimes",
    ]
    existing = _table_names(conn)
    return {
        table: [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY 1").fetchall()]
        for table in tables
        if table in existing
    }


def _seed_base(conn) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '设备一', 'active'), ('M2', '设备二', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '人员一', 'active'), ('O2', '人员二', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一'), ('P002', '零件二'), ('P003', '零件三');

        INSERT INTO Materials(material_id, name, spec, unit)
        VALUES ('MAT1', '主料', 'A', 'kg'), ('MAT2', '辅料', 'B', 'kg');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES
          ('B_SCHEDULED', 'P001', '零件一', 1, '2026-05-03', 'urgent', 'partial', 'scheduled'),
          ('B_UNSCHEDULED', 'P002', '零件二', 1, '2026-05-03', 'normal', 'yes', 'pending'),
          ('B_OK', 'P003', '零件三', 1, '2026-05-20', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES
          (10, 'OP-S-10', 'B_SCHEDULED', 'piece-a', 10, '车削', 'internal', 'scheduled'),
          (20, 'OP-S-20', 'B_SCHEDULED', 'piece-a', 20, '钻孔', 'internal', 'scheduled'),
          (30, 'OP-U-10', 'B_UNSCHEDULED', 'piece-b', 10, '铣削', 'internal', 'pending'),
          (40, 'OP-OK-10', 'B_OK', 'piece-c', 10, '磨削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (11);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
          (110, 10, 'M1', 'O1', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', 11),
          (120, 20, 'M1', 'O1', '2026-05-04 10:00:00', '2026-05-04 11:00:00', 'unlocked', 11),
          (140, 40, 'M2', 'O2', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', 11);

        INSERT INTO BatchMaterials(batch_id, material_id, required_qty, available_qty, ready_status)
        VALUES
          ('B_SCHEDULED', 'MAT1', 10, 0, 'no'),
          ('B_SCHEDULED', 'MAT2', 5, 1, NULL);

        INSERT INTO MachineDowntimes(machine_id, start_time, end_time, reason_code, status)
        VALUES ('M1', '2026-05-04 10:30:00', '2026-05-04 12:00:00', 'maintenance', 'active');

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (11, 'priority_first', 3, 4, 'success', '{}', 'pytest');
        """
    )


def _seed_db(tmp_path):
    conn = _connect(tmp_path)
    _seed_base(conn)
    conn.commit()
    return conn


def _overdue_rows(query, resolution):
    return query.list_plan_overdue_base_rows_for_resolution(
        version=resolution.version)


def test_overdue_official_source_remains_strict_and_rejects_retired_roles(tmp_path):
    conn = _seed_db(tmp_path)
    try:
        query = SchedulePlanQueryService(conn)
        before = _snapshot(conn)
        resolution = query.resolve_existing_plan(VERSION, ROLE_ADOPTED)
        assert resolution.source_table == SOURCE_SCHEDULE
        rows = _overdue_rows(query, resolution)
        assert next(row for row in rows if row['batch_id'] == 'B_SCHEDULED')['finish_time'] == '2026-05-04 11:00:00'
        assert _snapshot(conn) == before
        with pytest.raises(ValueError, match='未知的排产方案角色'):
            query.resolve_plan(VERSION, 'baseline_best')
        with pytest.raises(ValueError, match='未知的排产方案角色'):
            query.resolve_existing_plan(VERSION, 'baseline_best')
    finally:
        conn.close()


def test_overdue_allow_points_recognizes_zero_duration_point_event_batches(tmp_path):
    from datetime import datetime

    from core.services.common.overdue_calculations import compute_overdue_bucket_groups

    conn = _seed_db(tmp_path)
    try:
        conn.executescript(
            """
            INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
            VALUES
              ('B_PURE_POINT', 'P001', '零件一', 1, '2026-05-03', 'normal', 'yes', 'scheduled'),
              ('B_TAIL_POINT', 'P002', '零件二', 1, '2026-05-03', 'normal', 'yes', 'scheduled');

            INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
            VALUES
              (50, 'OP-PP-10', 'B_PURE_POINT', 'piece-pp', 10, '检验', 'internal', 'scheduled'),
              (60, 'OP-TP-10', 'B_TAIL_POINT', 'piece-tp', 10, '车削', 'internal', 'scheduled'),
              (70, 'OP-TP-20', 'B_TAIL_POINT', 'piece-tp', 20, '终检', 'internal', 'scheduled');

            INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
            VALUES
              (150, 50, 'M1', 'O1', '2026-05-04 12:00:00', '2026-05-04 12:00:00', 'unlocked', 11),
              (160, 60, 'M1', 'O1', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'unlocked', 11),
              (170, 70, 'M1', 'O1', '2026-05-04 15:30:00', '2026-05-04 15:30:00', 'unlocked', 11);
            """
        )
        conn.commit()
        query = SchedulePlanQueryService(conn)
        resolution = query.resolve_plan(VERSION, ROLE_ADOPTED)
        rows = query.list_plan_overdue_base_rows_for_resolution(
            version=resolution.version,
        )
        by_batch = {row["batch_id"]: row for row in rows}
        assert by_batch["B_PURE_POINT"]["finish_time"] == "2026-05-04 12:00:00"
        assert by_batch["B_PURE_POINT"]["invalid_time_count"] == 0
        assert by_batch["B_TAIL_POINT"]["finish_time"] == "2026-05-04 15:30:00"
        assert by_batch["B_TAIL_POINT"]["invalid_time_count"] == 0

        scheduled, unscheduled, invalid = compute_overdue_bucket_groups(
            rows, now_dt=datetime.fromisoformat(AS_OF_TIME)
        )
        assert not invalid
        assert {row["batch_id"] for row in unscheduled} == {"B_UNSCHEDULED"}
        assert {row["batch_id"] for row in scheduled} == {
            "B_SCHEDULED",
            "B_PURE_POINT",
            "B_TAIL_POINT",
        }
    finally:
        conn.close()


def test_cell_value_evaluates_active_section_for_multisection_number_formats():
    from types import SimpleNamespace

    from core.services.common.excel_cell_values import cell_value

    assert cell_value(SimpleNamespace(value=1, number_format="0;0%")) == 1
    assert cell_value(SimpleNamespace(value=-0.5, number_format="0;0%")) == -50.0
    assert cell_value(SimpleNamespace(value=0, number_format="0;0%;0.0")) == 0
    assert cell_value(SimpleNamespace(value=0.25, number_format="[<=1]0%;0.00")) == 25.0
    assert cell_value(SimpleNamespace(value=5, number_format="[<=1]0%;0.00")) == 5
    assert cell_value(SimpleNamespace(value=0.25, number_format=r'0\"%\"')) == 25
    assert cell_value(SimpleNamespace(value=0.25, number_format=r'0"%"')) == 0.25
