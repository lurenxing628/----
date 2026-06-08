"""回归测试：SchedulePlanQueryService.resolve_plan/resolve_plan_view 产出的 plan_identity 证据契约——当前 adopted 正式锁定计划可派工可回写反馈；失败/模拟的正式结果、历史旧版本、对比参考候选方案、回退到 adopted 的角色、场景预览方案均按规则禁派工/禁反馈并给出对应 user_label 与来源标记；build_plan_identity 缺 source_table 时抛 ValueError。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.infrastructure.errors import ValidationError
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_plan_identity_builder import build_plan_identity
from core.services.scheduler.schedule_plan_query_service import (
    ROLE_ADOPTED,
    ROLE_BASELINE_BEST,
    ROLE_CRITICAL_BEST,
    SchedulePlanQueryService,
)
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import (
    SOURCE_CANDIDATE_ROWS,
    SOURCE_SCHEDULE,
)
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
    "candidate_id",
    "candidate_key",
    "scenario_id",
    "schedule_result_status",
    "result_summary_parse_failed",
    "result_summary_parse_reason",
    "is_simulation",
    "label",
    "user_label",
    "is_official",
    "is_preview",
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
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _require_id(value):
    assert value is not None
    return int(value)


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


def _seed_candidates(conn) -> None:
    repo = ScheduleCandidateRepository(conn)
    adopted = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="adopted",
            candidate_label="最终采用",
            candidate_kind="baseline",
            status="completed",
            graph_enabled="no",
            detail_saved="no",
        )
    )
    baseline = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="baseline_best",
            candidate_label="原算法候选",
            candidate_kind="baseline",
            status="completed",
            graph_enabled="no",
            detail_saved="yes",
        )
    )
    baseline_id = _require_id(baseline.id)
    repo.bulk_create_candidate_rows(
        [
            ScheduleCandidateRows(
                id=None,
                version=VERSION,
                candidate_id=baseline_id,
                op_id=10,
                machine_id="M-CANDIDATE",
                operator_id="O-CANDIDATE",
                start_time="2026-05-05 13:00:00",
                end_time="2026-05-05 14:00:00",
                lock_status="locked",
            )
        ]
    )
    repo.create_selection(
        ScheduleCandidateSelection(
            id=None,
            version=VERSION,
            role=ROLE_ADOPTED,
            candidate_id=_require_id(adopted.id),
            source_table=SOURCE_SCHEDULE,
        )
    )
    repo.create_selection(
        ScheduleCandidateSelection(
            id=None,
            version=VERSION,
            role=ROLE_BASELINE_BEST,
            candidate_id=baseline_id,
            source_table=SOURCE_CANDIDATE_ROWS,
        )
    )


def _seed_scenario(conn) -> str:
    scenario_id = "scenario-plain"
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
            "draft-plain",
            VERSION,
            ROLE_ADOPTED,
            SOURCE_SCHEDULE,
            None,
            "adopted",
            "",
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
            80,
            10,
            "M-CANDIDATE",
            "O-CANDIDATE",
            "2026-05-06 08:00:00",
            "2026-05-06 09:00:00",
            "unlocked",
            "yes",
        ),
    )
    return scenario_id


def _seed_db(tmp_path):
    conn = _connect_fresh_schema(tmp_path)
    _seed_base(conn)
    _seed_candidates(conn)
    _seed_scenario(conn)
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
        assert identity["is_preview"] is False
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


@pytest.mark.parametrize(
    ("result_status", "result_summary"),
    [
        (None, "{}"),
        ("failed", "{}"),
        ("simulated", "{}"),
        ("success", '{"is_simulation": true}'),
    ],
)
def test_failed_or_simulated_official_result_cannot_dispatch_or_write_feedback(
    tmp_path,
    result_status,
    result_summary,
) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute(
            """
            UPDATE ScheduleHistory
               SET result_status = ?, result_summary = ?
             WHERE version = ?
            """,
            (result_status, result_summary, VERSION),
        )
        conn.commit()

        identity = _identity_dict(SchedulePlanQueryService(conn).resolve_plan(VERSION, ROLE_ADOPTED))

        assert identity["is_current_executable_official_version"] is False
        assert identity["can_dispatch"] is False
        assert identity["can_write_feedback"] is False
    finally:
        conn.close()


def test_bad_result_summary_fails_closed_for_official_identity(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        conn.execute(
            """
            UPDATE ScheduleHistory
               SET result_status = 'success', result_summary = ?
             WHERE version = ?
            """,
            ("{bad-json", VERSION),
        )
        conn.commit()

        identity = _identity_dict(SchedulePlanQueryService(conn).resolve_plan(VERSION, ROLE_ADOPTED))

        assert identity["result_summary_parse_failed"] is True
        assert identity["result_summary_parse_reason"]
        assert identity["is_simulation"] is True
        assert identity["is_current_executable_official_version"] is False
        assert identity["can_dispatch"] is False
        assert identity["can_write_feedback"] is False
    finally:
        conn.close()


def test_bad_plan_role_still_raises_with_plan_role_field() -> None:
    from core.services.scheduler.schedule_result_view_context import normalize_plan_role

    with pytest.raises(ValidationError) as exc_info:
        normalize_plan_role("bad_role")

    assert exc_info.value.field == "plan_role"


def test_history_candidate_fallback_and_same_source_comparison_cannot_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)
        history_identity = _identity_dict(service.resolve_plan(6, ROLE_ADOPTED))
        _assert_identity_fields(
            history_identity,
            {"is_superseded_by_newer_version": True, "can_dispatch": False, "can_write_feedback": False},
        )

        candidate_identity = _identity_dict(service.resolve_plan(VERSION, ROLE_BASELINE_BEST))
        _assert_identity_fields(
            candidate_identity,
            {
                "user_label": "对比参考方案",
                "source_table": SOURCE_CANDIDATE_ROWS,
                "detail_saved": True,
                "can_dispatch": False,
                "can_write_feedback": False,
            },
        )

        conn.execute(
            """
            UPDATE ScheduleCandidateSelection
               SET source_table = ?
             WHERE version = ? AND role = ?
            """,
            (SOURCE_SCHEDULE, VERSION, ROLE_BASELINE_BEST),
        )
        conn.commit()
        same_source_identity = _identity_dict(service.resolve_plan(VERSION, ROLE_BASELINE_BEST))
        _assert_identity_fields(
            same_source_identity,
            {
                "source_table": SOURCE_SCHEDULE,
                "user_label": "对比参考方案",
                "can_dispatch": False,
                "can_write_feedback": False,
            },
        )

        fallback_identity = _identity_dict(service.resolve_plan(VERSION, ROLE_CRITICAL_BEST))
        _assert_identity_fields(
            fallback_identity,
            {
                "plan_resolution_status": "fallback_to_adopted",
                "effective_plan_role": ROLE_ADOPTED,
                "can_write_feedback": False,
            },
        )
    finally:
        conn.close()


def test_scenario_preview_plan_identity_uses_plain_label_and_cannot_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        scenario_id = "scenario-plain"
        identity = _identity_dict(SchedulePlanQueryService(conn).resolve_plan_view(VERSION, ROLE_ADOPTED, scenario_id))

        assert identity["scenario_id"] == scenario_id
        assert identity["source_table"] == "adjustment_scenario_rows"
        assert identity["source_row_id"] is not None
        assert identity["user_label"] == "模拟预览（未命名）"
        assert identity["is_official"] is False
        assert identity["is_preview"] is True
        assert identity["is_simulation"] is True
        assert identity["can_dispatch"] is False
        assert identity["can_write_feedback"] is False
    finally:
        conn.close()


def test_plan_identity_builder_rejects_missing_source_table() -> None:
    with pytest.raises(ValueError, match="有效的数据来源"):
        build_plan_identity(
            version=VERSION,
            requested_role=ROLE_ADOPTED,
            effective_role=ROLE_ADOPTED,
            status="resolved_adopted",
            source_table="",
            source_row_id=80,
            candidate_id=None,
            candidate_key=None,
            scenario_id=None,
            scenario_display_name="",
            schedule_result_status="success",
            result_summary="{}",
            latest_official_version=VERSION,
            schedule_lock_status="unlocked",
            detail_saved="yes",
        )
