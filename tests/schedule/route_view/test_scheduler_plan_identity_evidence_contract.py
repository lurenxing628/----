"""正式方案可派工反馈，历史版本和对比方案回退拒绝写入。"""

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
VERSION = 7
EXPECTED_PLAN_IDENTITY_KEYS = (
    "version",
    "requested_plan_role",
    "effective_plan_role",
    "plan_resolution_status",
    "source_table",
    "source_row_id",
    "schedule_result_status",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
    "is_simulation",
    "label",
    "user_label",
    "is_official",
    "is_current_executable_version",
    "is_current_executable_official_version",
    "is_superseded_by_newer_version",
    "schedule_lock_status",
    "can_dispatch",
    "can_write_feedback",
    "detail_saved",
)


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


def _identity_dict(resolution):
    data = resolution.to_dict()
    identity = data["plan_identity"]
    assert tuple(identity) == EXPECTED_PLAN_IDENTITY_KEYS
    return identity


def _assert_identity_fields(identity: dict, expected: dict) -> None:
    assert {key: identity[key] for key in expected} == expected


def test_current_adopted_plan_identity_can_dispatch_and_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute("UPDATE Schedule SET lock_status = 'locked' WHERE version = ? AND id = 80", (VERSION,))
        conn.commit()
        identity = _identity_dict(SchedulePlanQueryService(conn).resolve_plan(VERSION, ROLE_ADOPTED))

        assert identity["requested_plan_role"] == ROLE_ADOPTED
        assert identity["effective_plan_role"] == ROLE_ADOPTED
        assert identity["plan_resolution_status"] == "resolved_adopted"
        assert identity["source_table"] == SOURCE_SCHEDULE
        assert identity["source_row_id"] == 80
        assert identity["user_label"] == "正式采用方案"
        assert identity["is_official"] is True
        assert identity["is_current_executable_version"] is True
        assert identity["is_current_executable_official_version"] is True
        assert identity["is_superseded_by_newer_version"] is False
        assert identity["result_summary_parse_failed"] is False
        assert identity["result_summary_parse_reason"] == ""
        assert identity["schedule_lock_status"] == "locked"
        assert identity["can_dispatch"] is True
        assert identity["can_write_feedback"] is True
    finally:
        conn.close()


def test_history_and_comparison_role_fallback_cannot_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)
        history_identity = _identity_dict(service.resolve_plan(6, ROLE_ADOPTED))
        _assert_identity_fields(
            history_identity,
            {"is_superseded_by_newer_version": True, "can_dispatch": False, "can_write_feedback": False},
        )

        for role in ("baseline_best", "critical_best"):
            with pytest.raises(ValueError, match="未知的排产方案角色"):
                service.resolve_plan(VERSION, role)
    finally:
        conn.close()
