from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.models.schedule_plan_identity import EvidenceLink
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

REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 7


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
    assert set(identity) >= {
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
    }
    return identity


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
        assert identity["schedule_lock_status"] == "locked"
        assert identity["can_dispatch"] is True
        assert identity["can_write_feedback"] is True
    finally:
        conn.close()


@pytest.mark.parametrize(
    ("result_status", "result_summary"),
    [
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


def test_history_candidate_fallback_and_same_source_comparison_cannot_write_feedback(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        service = SchedulePlanQueryService(conn)
        history_identity = _identity_dict(service.resolve_plan(6, ROLE_ADOPTED))
        assert history_identity["is_superseded_by_newer_version"] is True
        assert history_identity["can_dispatch"] is False
        assert history_identity["can_write_feedback"] is False

        candidate_identity = _identity_dict(service.resolve_plan(VERSION, ROLE_BASELINE_BEST))
        assert candidate_identity["user_label"] == "对比参考方案"
        assert candidate_identity["source_table"] == SOURCE_CANDIDATE_ROWS
        assert candidate_identity["detail_saved"] is True
        assert candidate_identity["can_dispatch"] is False
        assert candidate_identity["can_write_feedback"] is False

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
        assert same_source_identity["source_table"] == SOURCE_SCHEDULE
        assert same_source_identity["user_label"] == "对比参考方案"
        assert same_source_identity["can_dispatch"] is False
        assert same_source_identity["can_write_feedback"] is False

        fallback_identity = _identity_dict(service.resolve_plan(VERSION, ROLE_CRITICAL_BEST))
        assert fallback_identity["plan_resolution_status"] == "fallback_to_adopted"
        assert fallback_identity["effective_plan_role"] == ROLE_ADOPTED
        assert fallback_identity["can_write_feedback"] is False
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


def test_evidence_link_validates_row_aggregate_and_missing_data_scopes(tmp_path) -> None:
    conn = _seed_db(tmp_path)
    try:
        identity_obj = SchedulePlanQueryService(conn).resolve_plan(VERSION, ROLE_ADOPTED).plan_identity
        assert identity_obj is not None

        row_evidence = EvidenceLink(
            evidence_type="schedule_row",
            evidence_label="正式排程明细",
            object_type="schedule",
            object_id=80,
            plan_identity=identity_obj,
            source_table=SOURCE_SCHEDULE,
            source_row_id=80,
            evidence_scope="row",
            source_page="设备甘特图",
            link="/scheduler/gantt?version=7&plan_role=adopted",
        )
        assert row_evidence.to_dict()["source_row_id"] == 80

        aggregate_evidence = EvidenceLink(
            evidence_type="utilization",
            evidence_label="设备负荷汇总",
            object_type="machine",
            object_id="M-ADOPTED",
            plan_identity=identity_obj,
            source_table=None,
            source_row_id=None,
            evidence_scope="aggregate",
            aggregation_key="machine:M-ADOPTED",
            contributing_count=3,
            source_page="资源负荷",
        )
        assert aggregate_evidence.to_dict()["contributing_count"] == 3

        with pytest.raises(ValueError, match="来源表不可信"):
            EvidenceLink(
                evidence_type="utilization",
                evidence_label="假汇总来源",
                object_type="machine",
                object_id="M-ADOPTED",
                plan_identity=identity_obj,
                source_table="fake_table",
                source_row_id=None,
                evidence_scope="aggregate",
                aggregation_key="machine:M-ADOPTED",
                contributing_count=3,
                source_page="测试",
            ).to_dict()

        missing_evidence = EvidenceLink(
            evidence_type="material_ready",
            evidence_label="缺少齐套明细",
            object_type="batch",
            object_id="B1",
            plan_identity=identity_obj,
            source_table=None,
            source_row_id=None,
            evidence_scope="missing_data",
            missing_data_key="batch_materials_missing",
            expected_source="BatchMaterials",
            checked_object_type="batch",
            checked_object_id="B1",
            checked_at="2026-05-26 10:00:00",
            gap_label="缺少批次 B1 的物料明细，暂时不能判断是不是物料问题。",
            source_page="超期清单",
            confidence="missing_data",
        )
        assert missing_evidence.to_dict()["gap_label"].startswith("缺少批次")

        with pytest.raises(ValueError, match="来源表不可信"):
            EvidenceLink(
                evidence_type="material_ready",
                evidence_label="假缺口来源",
                object_type="batch",
                object_id="B1",
                plan_identity=identity_obj,
                source_table="fake_table",
                source_row_id=None,
                evidence_scope="missing_data",
                missing_data_key="batch_materials_missing",
                expected_source="BatchMaterials",
                checked_object_type="batch",
                checked_object_id="B1",
                checked_at="2026-05-26 10:00:00",
                gap_label="缺少批次 B1 的物料明细，暂时不能判断是不是物料问题。",
                source_page="测试",
                confidence="missing_data",
            ).to_dict()

        with pytest.raises(ValueError, match="行级证据"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="坏证据",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=None,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
            ).to_dict()

        with pytest.raises(ValueError, match="来源表不可信"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="假来源",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table="fake_table",
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
            ).to_dict()

        with pytest.raises(ValueError, match="当前计划版本"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="坏链接",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?plan_role=adopted",
            ).to_dict()

        with pytest.raises(ValueError, match="当前方案"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="坏链接",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=baseline_best",
            ).to_dict()

        with pytest.raises(ValueError, match="当前计划版本"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="混入别的版本",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&version=8&plan_role=adopted",
            ).to_dict()

        with pytest.raises(ValueError, match="当前计划版本"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="混入空版本",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&version=&plan_role=adopted",
            ).to_dict()

        with pytest.raises(ValueError, match="当前计划版本"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="重复相同版本",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&version=7&plan_role=adopted",
            ).to_dict()

        with pytest.raises(ValueError, match="当前方案"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="混入别的方案",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=adopted&plan_role=baseline_best",
            ).to_dict()

        with pytest.raises(ValueError, match="当前方案"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="混入空方案",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=adopted&plan_role=%20",
            ).to_dict()

        with pytest.raises(ValueError, match="当前模拟预览"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="正式方案混入模拟编号",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=adopted&scenario_id=scenario-other",
            ).to_dict()

        with pytest.raises(ValueError, match="当前模拟预览"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="正式方案混入空模拟编号",
                object_type="schedule",
                object_id=80,
                plan_identity=identity_obj,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=adopted&scenario_id=",
            ).to_dict()

        scenario_identity = SchedulePlanQueryService(conn).resolve_plan_view(
            VERSION,
            ROLE_ADOPTED,
            "scenario-plain",
        ).plan_identity
        assert scenario_identity is not None
        with pytest.raises(ValueError, match="当前模拟预览"):
            EvidenceLink(
                evidence_type="schedule_row",
                evidence_label="坏模拟链接",
                object_type="schedule",
                object_id=80,
                plan_identity=scenario_identity,
                source_table=SOURCE_SCHEDULE,
                source_row_id=80,
                evidence_scope="row",
                source_page="测试",
                link="/scheduler/gantt?version=7&plan_role=adopted",
            ).to_dict()

        with pytest.raises(ValueError, match="缺数据证据"):
            EvidenceLink(
                evidence_type="material_ready",
                evidence_label="坏缺口",
                object_type="batch",
                object_id="B1",
                plan_identity=identity_obj,
                source_table=None,
                source_row_id=None,
                evidence_scope="missing_data",
                source_page="测试",
                confidence="missing_data",
            ).to_dict()

        with pytest.raises(ValueError, match="当前数据不足"):
            EvidenceLink(
                evidence_type="material_ready",
                evidence_label="坏缺口等级",
                object_type="batch",
                object_id="B1",
                plan_identity=identity_obj,
                source_table=None,
                source_row_id=None,
                evidence_scope="missing_data",
                missing_data_key="batch_materials_missing",
                expected_source="BatchMaterials",
                checked_object_type="batch",
                checked_object_id="B1",
                checked_at="2026-05-26 10:00:00",
                gap_label="缺少批次 B1 的物料明细，暂时不能判断是不是物料问题。",
                source_page="测试",
            ).to_dict()
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
