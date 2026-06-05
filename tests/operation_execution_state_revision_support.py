from __future__ import annotations

import sqlite3
from pathlib import Path

from core.infrastructure.database import ensure_schema, get_connection
from core.services.scheduler.operation_execution_feedback_service import ExecutionFeedbackContext
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED
from data.repositories.schedule_plan_query_repo import SOURCE_SCHEDULE

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"


def _connect(tmp_path: Path) -> sqlite3.Connection:
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _prepare_db(tmp_path: Path, name: str = "aps.db") -> Path:
    db_path = tmp_path / name
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    conn = get_connection(str(db_path))
    try:
        _seed_plan(conn)
    finally:
        conn.close()
    return db_path


def _seed_plan(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M1', '一号设备', 'active'), ('M2', '二号设备', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O1', '张三', 'active'), ('O2', '李四', 'active');

        INSERT INTO Parts(part_no, part_name)
        VALUES ('P001', '零件一');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 10, '2026-05-10', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO ScheduleVersionSeq(version) VALUES (1);

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES (100, 10, 'M1', 'O1', '2026-05-01 08:00:00', '2026-05-01 09:00:00', 'unlocked', 1);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES (1, 'priority_first', 1, 1, 'success', '{}', 'pytest');
        """
    )
    conn.commit()


def _context(**overrides) -> ExecutionFeedbackContext:
    data = {
        "schedule_version": 1,
        "schedule_id": 100,
        "op_id": 10,
        "batch_id": "B1",
        "expected_state_revision": "10:0:0",
        "created_by": "张三",
        "idempotency_key": "start-key",
        "requested_plan_role": ROLE_ADOPTED,
        "source_table": SOURCE_SCHEDULE,
        "effective_plan_role": ROLE_ADOPTED,
        "scenario_id": None,
    }
    data.update(overrides)
    return ExecutionFeedbackContext(**data)


def _event_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(1) AS count FROM OperationExecutionEvents").fetchone()
    return int(row["count"])


def _event_count_from_path(db_path: Path) -> int:
    conn = get_connection(str(db_path))
    try:
        return _event_count(conn)
    finally:
        conn.close()
