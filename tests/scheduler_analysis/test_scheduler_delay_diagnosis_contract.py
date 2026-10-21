"""Overdue calculations preserve source identity and invalid-time buckets."""

from __future__ import annotations

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_plan_role import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
)
from core.services.common.plan_query import SchedulePlanQueryService
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 11
AS_OF_TIME = "2026-05-05 12:00:00"


def _connect(tmp_path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _table_names(conn):
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()
    return {str(row["name"]) for row in rows}


def _snapshot(conn):
    tables = [
        "Schedule",
        "ScheduleHistory",
        "ScheduleVersionSeq",
        "ScheduleCandidate",
        "ScheduleCandidateRows",
        "ScheduleCandidateSelection",
        "ScheduleAdjustmentDraft",
        "ScheduleAdjustmentChange",
        "ScheduleAdjustmentScenario",
        "ScheduleAdjustmentScenarioRow",
        "Materials",
        "Batches",
        "BatchMaterials",
        "MachineDowntimes",
    ]
    existing = _table_names(conn)
    if "OperationExecutionEvents" in existing:
        tables.append("OperationExecutionEvents")
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


def _seed_candidates(conn) -> int:
    adopted_id = conn.execute(
        "INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status,graph_enabled,detail_saved) "
        "VALUES (?,'adopted',?,'baseline','completed','no','no')", (VERSION, '正式采用'),
    ).lastrowid
    baseline_id = conn.execute(
        "INSERT INTO ScheduleCandidate(version,candidate_key,candidate_label,candidate_kind,status,graph_enabled,detail_saved) "
        "VALUES (?,'baseline_best','原算法候选','baseline','completed','no','yes')", (VERSION,),
    ).lastrowid
    assert adopted_id is not None and baseline_id is not None
    conn.executemany(
        "INSERT INTO ScheduleCandidateRows(version,candidate_id,op_id,machine_id,operator_id,start_time,end_time,lock_status) "
        "VALUES (?,?,?,?,?,?,?,'locked')",
        [(VERSION, baseline_id, *row) for row in [
            (10, 'M2', 'O2', '2026-05-04 12:00:00', '2026-05-04 13:00:00'),
            (20, 'M2', 'O2', '2026-05-04 13:00:00', '2026-05-04 14:00:00')
        ]],
    )
    conn.executemany(
        "INSERT INTO ScheduleCandidateSelection(version,role,candidate_id,source_table) VALUES (?,?,?,?)",
        [(VERSION, ROLE_ADOPTED, adopted_id, SOURCE_SCHEDULE),
         (VERSION, ROLE_BASELINE_BEST, baseline_id, SOURCE_CANDIDATE_ROWS)],
    )
    return baseline_id


def _seed_scenario(conn) -> str:
    scenario_id = "delay-preview"
    base = SchedulePlanQueryService(conn).resolve_existing_plan(VERSION, ROLE_ADOPTED)
    conn.execute(
        """
        INSERT INTO ScheduleAdjustmentScenario(
            scenario_id, source_draft_id, base_version, base_plan_role,
            base_source_table, base_candidate_id, base_candidate_key,
            scenario_name, status, validation_status, issue_count, row_count, created_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scenario_id,
            "draft-delay-preview",
            VERSION,
            ROLE_ADOPTED,
            base.source_table,
            base.candidate_id,
            base.candidate_key,
            "延期诊断预览",
            "active",
            "valid",
            0,
            1,
            "pytest",
        ),
    )
    conn.execute(
        """
        INSERT INTO ScheduleAdjustmentScenarioRow(
            scenario_id, source_table, source_row_id, op_id, machine_id, operator_id,
            start_time, end_time, lock_status, is_changed
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            scenario_id,
            SOURCE_SCHEDULE,
            120,
            20,
            "M2",
            "O2",
            "2026-05-04 15:00:00",
            "2026-05-04 16:00:00",
            "unlocked",
            "yes",
        ),
    )
    return scenario_id


def _seed_db(tmp_path):
    conn = _connect(tmp_path)
    _seed_base(conn)
    _seed_candidates(conn)
    scenario_id = _seed_scenario(conn)
    conn.commit()
    return conn, scenario_id


def _overdue_rows(query, resolution):
    return query.list_plan_overdue_base_rows_for_resolution(
        version=resolution.version, source_table=resolution.source_table,
        candidate_id=resolution.candidate_id, scenario_id=resolution.scenario_id)


def test_overdue_bad_finish_time_has_its_own_bucket(tmp_path):
    from datetime import datetime

    from core.services.common.overdue_calculations import compute_overdue_bucket_groups

    conn, _ = _seed_db(tmp_path)
    try:
        conn.execute("UPDATE Schedule SET end_time='坏结束时间' WHERE op_id IN (SELECT id FROM BatchOperations WHERE batch_id='B_SCHEDULED')")
        conn.commit()
        query = SchedulePlanQueryService(conn)
        resolution = query.resolve_plan_view(VERSION, ROLE_ADOPTED)
        scheduled, unscheduled, invalid, _ = compute_overdue_bucket_groups(
            _overdue_rows(query, resolution), now_dt=datetime.fromisoformat(AS_OF_TIME))
        assert not scheduled
        assert {row['batch_id'] for row in unscheduled} == {'B_UNSCHEDULED'}
        assert {row['batch_id'] for row in invalid} == {'B_SCHEDULED'}
        assert invalid[0]['bucket'] == 'schedule_time_invalid'
    finally:
        conn.close()


def test_overdue_candidate_source_remains_strict_and_read_only(tmp_path):
    conn, _ = _seed_db(tmp_path)
    try:
        query = SchedulePlanQueryService(conn)
        before = _snapshot(conn)
        resolution = query.resolve_existing_plan(VERSION, ROLE_BASELINE_BEST)
        assert resolution.source_table == SOURCE_CANDIDATE_ROWS
        rows = _overdue_rows(query, resolution)
        assert next(row for row in rows if row['batch_id'] == 'B_SCHEDULED')['finish_time'] == '2026-05-04 14:00:00'
        assert _snapshot(conn) == before
        conn.execute('DELETE FROM ScheduleCandidateRows')
        conn.commit()
        with pytest.raises(ValueError, match='所选方案没有可查看的明细'):
            query.resolve_existing_plan(VERSION, ROLE_BASELINE_BEST)
        with pytest.raises(ValueError, match='方案对比明细没有找到对应排程'):
            query.resolve_plan_view(VERSION, ROLE_BASELINE_BEST)
        conn.execute('DELETE FROM ScheduleCandidateSelection')
        conn.execute('DELETE FROM ScheduleCandidate')
        conn.commit()
        fallback = query.resolve_plan_view(VERSION, ROLE_BASELINE_BEST)
        assert fallback.status == 'fallback_to_adopted'
        with pytest.raises(ValueError, match='所选方案不存在'):
            query.resolve_existing_plan(VERSION, ROLE_BASELINE_BEST)
    finally:
        conn.close()


def test_overdue_scenario_source_remains_strict_and_read_only(tmp_path):
    conn, scenario_id = _seed_db(tmp_path)
    try:
        query = SchedulePlanQueryService(conn)
        before = _snapshot(conn)
        resolution = query.resolve_plan_view(VERSION, ROLE_ADOPTED, scenario_id)
        assert resolution.source_table == 'adjustment_scenario_rows'
        rows = _overdue_rows(query, resolution)
        assert next(row for row in rows if row['batch_id'] == 'B_SCHEDULED')['finish_time'] == '2026-05-04 16:00:00'
        assert _snapshot(conn) == before
        conn.execute('DELETE FROM ScheduleAdjustmentScenarioRow WHERE scenario_id=?', (scenario_id,))
        conn.commit()
        with pytest.raises(ValueError, match='模拟方案明细不存在'):
            query.resolve_plan_view(VERSION, ROLE_ADOPTED, scenario_id)
    finally:
        conn.close()
