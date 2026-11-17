"""当前正式方案可写现场反馈；历史版本或缺少正式证据的最新方案拒绝写入。"""

from __future__ import annotations

import logging

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_plan_identity import PlanIdentity
from core.services.common.plan_query import SchedulePlanQueryService
from tests._support.paths import REPO_ROOT
from tests.workbench.plan_catalog_support import ensure_history_head, insert_schedule_row

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7


def _connect_fresh_schema(tmp_path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), logging.getLogger(__name__), schema_path=str(SCHEMA_PATH))
    return get_connection(str(db_path))


def _seed_base(conn, *, v7_status: str = "success", seed_v7_rows: bool = True) -> None:
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
        """
    )
    ensure_history_head(conn, 6, strategy="greedy", schedule_time="2026-05-04T08:00:00", created_by="pytest")
    insert_schedule_row(
        conn, 6, 10, "2026-05-04T08:00:00", "2026-05-04T09:00:00",
        schedule_id=70, machine_id="M-ADOPTED", operator_id="O-ADOPTED", lock_status="locked",
    )
    ensure_history_head(
        conn, 7, strategy="greedy", schedule_time="2026-05-05T08:00:00", status=v7_status, created_by="pytest"
    )
    if seed_v7_rows:
        insert_schedule_row(
            conn, 7, 10, "2026-05-05T08:00:00", "2026-05-05T09:00:00",
            schedule_id=80, machine_id="M-ADOPTED", operator_id="O-ADOPTED", lock_status="unlocked",
        )


def _seed_db(tmp_path, *, v7_status: str = "success", seed_v7_rows: bool = True):
    conn = _connect_fresh_schema(tmp_path)
    _seed_base(conn, v7_status=v7_status, seed_v7_rows=seed_v7_rows)
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
    ("v7_status", "seed_v7_rows"),
    [
        pytest.param("failed", True, id="result_not_success"),
        pytest.param("success", False, id="no_schedule_rows"),
    ],
)
def test_latest_plan_without_official_evidence_cannot_write_feedback(
    tmp_path, v7_status: str, seed_v7_rows: bool
) -> None:
    conn = _seed_db(tmp_path, v7_status=v7_status, seed_v7_rows=seed_v7_rows)
    try:
        assert _identity(conn, VERSION) == PlanIdentity(
            version=VERSION,
            is_current_executable_official_version=False,
            can_write_feedback=False,
        )
    finally:
        conn.close()
