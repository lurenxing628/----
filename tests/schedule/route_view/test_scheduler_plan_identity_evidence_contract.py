"""当前正式方案可写现场反馈；历史版本或缺少正式证据的最新方案拒绝写入。"""

from __future__ import annotations

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_plan_identity import PlanIdentity
from core.services.common.plan_query import SchedulePlanQueryService
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7


def _connect_fresh_schema(tmp_path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH))
    return get_connection(str(db_path))


def _seed_base(conn) -> None:
    conn.executescript(
        """
        INSERT INTO Machines(machine_id, name, status)
        VALUES ('M-ADOPTED', '正式设备', 'active'), ('M-CANDIDATE', '候选设备', 'active');

        INSERT INTO Operators(operator_id, name, status)
        VALUES ('O-ADOPTED', '正式人员', 'active'), ('O-CANDIDATE', '候选人员', 'active');

        INSERT INTO Parts(part_no, part_name, route_parsed)
        VALUES ('P001', '零件一', 'yes');

        INSERT INTO Batches(batch_id, part_no, part_name, quantity, due_date, priority, ready_status, status)
        VALUES ('B1', 'P001', '零件一', 1, '2026-05-20', 'normal', 'yes', 'scheduled');

        INSERT INTO BatchOperations(id, op_code, batch_id, piece_id, seq, op_type_name, source, status)
        VALUES (10, 'OP10', 'B1', 'piece-a', 10, '车削', 'internal', 'scheduled');

        INSERT INTO Schedule(id, op_id, machine_id, operator_id, start_time, end_time, lock_status, version)
        VALUES
          (70, 10, 'M-ADOPTED', 'O-ADOPTED', '2026-05-04 08:00:00', '2026-05-04 09:00:00', 'locked', 6),
          (80, 10, 'M-ADOPTED', 'O-ADOPTED', '2026-05-05 08:00:00', '2026-05-05 09:00:00', 'unlocked', 7);

        INSERT INTO ScheduleHistory(version, strategy, batch_count, op_count, result_status, result_summary, created_by)
        VALUES
          (6, 'greedy', 1, 1, 'success', '{}', 'pytest'),
          (7, 'greedy', 1, 1, 'success', '{}', 'pytest');
        """
    )


def _seed_db(tmp_path):
    conn = _connect_fresh_schema(tmp_path)
    _seed_base(conn)
    conn.commit()
    return conn


def _identity(conn, version: int) -> PlanIdentity:
    return SchedulePlanQueryService(conn).resolve_plan(version).plan_identity


def test_current_adopted_plan_identity_can_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        assert _identity(conn, VERSION) == PlanIdentity(
            version=VERSION,
            is_current_executable_official_version=True,
            can_write_feedback=True,
        )
    finally:
        conn.close()


def test_superseded_history_plan_cannot_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        assert _identity(conn, 6) == PlanIdentity(
            version=6,
            is_current_executable_official_version=False,
            can_write_feedback=False,
        )
    finally:
        conn.close()


@pytest.mark.parametrize(
    "mutation",
    [
        pytest.param("UPDATE ScheduleHistory SET result_summary = '{\"is_simulation\": true}' WHERE version = 7", id="simulation"),
        pytest.param("UPDATE ScheduleHistory SET result_summary = '{bad' WHERE version = 7", id="summary_malformed"),
        pytest.param("UPDATE ScheduleHistory SET result_summary = NULL WHERE version = 7", id="summary_missing"),
        pytest.param("UPDATE ScheduleHistory SET result_status = 'failed' WHERE version = 7", id="result_not_success"),
        pytest.param("DELETE FROM Schedule WHERE version = 7", id="no_schedule_rows"),
    ],
)
def test_latest_plan_without_official_evidence_cannot_write_feedback(tmp_path, mutation: str) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute(mutation)
        conn.commit()
        assert _identity(conn, VERSION) == PlanIdentity(
            version=VERSION,
            is_current_executable_official_version=False,
            can_write_feedback=False,
        )
    finally:
        conn.close()
