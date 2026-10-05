"""在制工序约束后续排程，执行状态变化使持久化事务回滚。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import core.services.scheduler.run.schedule_persistence as schedule_persistence_mod
import core.services.scheduler.schedule_service as schedule_service_mod
from core.errors import AppError
from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_plan_role import ROLE_ADOPTED, SOURCE_SCHEDULE
from core.services.scheduler.operation_execution_feedback_service import (
    ExecutionFeedbackContext,
    OperationExecutionFeedbackService,
)
from core.services.scheduler.schedule_service import ScheduleService
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps_reschedule_execution_guardrails.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _seed_two_operation_plan(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO ResourceTeams(team_id, name, status)
        VALUES ('T1', '一组', 'active');

        INSERT INTO Machines(machine_id, name, status, team_id)
        VALUES ('M1', '一号设备', 'active', 'T1'), ('M2', '二号设备', 'active', 'T1');

        INSERT INTO Operators(operator_id, name, status, team_id)
        VALUES ('O1', '张三', 'active', 'T1'), ('O2', '李四', 'active', 'T1');

        INSERT INTO OperatorMachine(operator_id, machine_id)
        VALUES ('O1', 'M1'), ('O2', 'M2');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(
            id, op_code, batch_id, piece_id, seq, op_type_name, source,
            machine_id, operator_id, setup_hours, unit_hours, status
        )
        VALUES
            (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'M1', 'O1', 0, 1, 'scheduled'),
            (20, 'OP20', 'B1', 'piece-b', 20, '铣削', 'internal', 'M2', 'O2', 0, 1, 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
            (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 1),
            (101, 20, 'M2', 'O2', '2026-05-01 09:00:00', '2026-05-01 10:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 1, 2, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def _context(*, op_id: int = 10, schedule_id: int = 100, revision: str = "10:0:0", key: str = "start-key"):
    return ExecutionFeedbackContext(
        schedule_version=1,
        schedule_id=schedule_id,
        op_id=op_id,
        batch_id="B1",
        expected_state_revision=revision,
        created_by="张三",
        idempotency_key=key,
        requested_plan_role=ROLE_ADOPTED,
        source_table=SOURCE_SCHEDULE,
        effective_plan_role=ROLE_ADOPTED,
        scenario_id=None,
    )


def _schedule_rows(conn: sqlite3.Connection, version: int):
    rows = conn.execute(
        """
        SELECT op_id, machine_id, operator_id, start_time, end_time, lock_status
        FROM Schedule
        WHERE version = ?
        ORDER BY op_id
        """,
        (int(version),),
    ).fetchall()
    return {int(row["op_id"]): dict(row) for row in rows}


def _counts(conn: sqlite3.Connection):
    return {
        "schedule": int(conn.execute("SELECT COUNT(1) FROM Schedule").fetchone()[0]),
        "history": int(conn.execute("SELECT COUNT(1) FROM ScheduleHistory").fetchone()[0]),
        "version_seq": int(conn.execute("SELECT COALESCE(MAX(version), 0) FROM ScheduleVersionSeq").fetchone()[0]),
    }


def test_processing_operation_is_fixed_and_downstream_starts_after_estimated_end(tmp_path: Path) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        feedback = OperationExecutionFeedbackService(conn)
        feedback.start_operation(
            _context(),
            event_time="2026-05-01 08:30:00",
            operator_id="O1",
            machine_id="M1",
            remark="现场已经开工",
        )

        result = ScheduleService(conn).run_schedule(
            ["B1"],
            start_dt="2026-05-01 08:00:00",
            created_by="pytest",
        )

        rows = _schedule_rows(conn, int(result["version"]))
        assert rows[10]["start_time"] == "2026-05-01 08:30:00"
        assert rows[10]["machine_id"] == "M1"
        assert rows[10]["operator_id"] == "O1"
        assert rows[10]["lock_status"] == "locked"
        assert rows[20]["start_time"] >= rows[10]["end_time"]
    finally:
        conn.close()


def test_late_execution_change_rolls_back_allocated_version(tmp_path: Path, monkeypatch) -> None:
    conn = _connect(tmp_path)
    try:
        _seed_two_operation_plan(conn)
        before = _counts(conn)
        original_service_validate = schedule_service_mod.validate_execution_guard_before_persist
        original_persist_validate = schedule_persistence_mod.validate_execution_guard_before_persist
        calls = {"service": 0, "persist": 0}

        def service_validate(*args, **kwargs):
            calls["service"] += 1
            return original_service_validate(*args, **kwargs)

        def persist_validate(*args, **kwargs):
            calls["persist"] += 1
            if calls["persist"] == 1:
                OperationExecutionFeedbackService(conn).start_operation(
                    _context(),
                    event_time="2026-05-01 08:30:00",
                    operator_id="O1",
                    machine_id="M1",
                )
            return original_persist_validate(*args, **kwargs)

        monkeypatch.setattr(schedule_service_mod, "validate_execution_guard_before_persist", service_validate)
        monkeypatch.setattr(schedule_persistence_mod, "validate_execution_guard_before_persist", persist_validate)

        with pytest.raises(AppError) as exc_info:
            ScheduleService(conn).run_schedule(
                ["B1"],
                start_dt="2026-05-01 08:00:00",
                created_by="pytest",
            )

        assert exc_info.value.code.value == "6003"
        assert exc_info.value.details["reason"] == "execution_state_changed"
        assert _counts(conn) == before
        assert int(conn.execute("SELECT COUNT(1) FROM OperationExecutionEvents").fetchone()[0]) == 0
        assert calls == {"service": 1, "persist": 1}
    finally:
        conn.close()
