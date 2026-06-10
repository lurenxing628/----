"""回归测试：延期诊断活门 diagnose_resolved_plan_overdue（R14/G41 收口后唯一入口，resolution 经 plan_query 喂入）只读地诊断超期（前后表快照不变），按 plan_role 从 Schedule/候选行/场景行三种来源取明细并产出含物料未齐/停机影响/建议工序线索、证据 link、trace_meta 指纹等结构化证据，不输出根因/critical_chain/primary_reason 等内部字段。灵魂线钉层（O21/O22）：候选「无静默回退」断言钉在 resolve_existing_plan 层（缺明细抛「所选方案没有可查看的明细」，禁平移到活门 diagnose 入口——活门非 scenario 走 resolve_plan 会 fallback_to_adopted 静默吞掉 raise）；scenario 断言平移到 resolve_plan_view（缺明细抛「模拟方案明细不存在」，两门同源）；另显式钉死「活门非 scenario 缺角色→fallback_to_adopted 不 raise」的死/活差异，防后人误以为两路等价。旧死门三件套 diagnose_plan_overdue/diagnose_batch/_resolve_strict_plan 已删。"""

from __future__ import annotations

from pathlib import Path

import pytest

from core.infrastructure.database import ensure_schema, get_connection
from core.models.schedule_candidate import ScheduleCandidate, ScheduleCandidateRows, ScheduleCandidateSelection
from core.services.scheduler.schedule_delay_diagnosis_service import ScheduleDelayDiagnosisService
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST
from data.repositories.schedule_candidate_repo import ScheduleCandidateRepository
from data.repositories.schedule_plan_query_repo import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from tests._support.paths import REPO_ROOT

SCHEMA_PATH = REPO_ROOT / "schema.sql"
VERSION = 11
AS_OF_TIME = "2026-05-05 12:00:00"


def _connect(tmp_path):
    db_path = tmp_path / "aps.db"
    ensure_schema(str(db_path), schema_path=str(SCHEMA_PATH), backup_dir=str(tmp_path / "backups"))
    return get_connection(str(db_path))


def _require_id(value):
    assert value is not None
    return int(value)


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
    repo = ScheduleCandidateRepository(conn)
    adopted = repo.create_candidate(
        ScheduleCandidate(
            id=None,
            version=VERSION,
            candidate_key="adopted",
            candidate_label="正式采用",
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
                machine_id="M2",
                operator_id="O2",
                start_time="2026-05-04 12:00:00",
                end_time="2026-05-04 13:00:00",
                lock_status="locked",
            ),
            ScheduleCandidateRows(
                id=None,
                version=VERSION,
                candidate_id=baseline_id,
                op_id=20,
                machine_id="M2",
                operator_id="O2",
                start_time="2026-05-04 13:00:00",
                end_time="2026-05-04 14:00:00",
                lock_status="locked",
            ),
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
    return baseline_id


def _seed_scenario(conn) -> str:
    scenario_id = "delay-preview"
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
            SOURCE_SCHEDULE,
            None,
            "adopted",
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


def _item_by_batch(report, batch_id):
    for item in report.items:
        if item.batch_id == batch_id:
            return item
    raise AssertionError(f"没有找到批次：{batch_id}")


def _clue_codes(item):
    return {clue.clue_code for clue in item.candidate_clues}


def _diagnose_via_live_door(service: ScheduleDelayDiagnosisService, *, plan_role: str, scenario_id=None):
    # 生产现行路径：report_engine → resolve_plan_view 喂 resolution → 活门 diagnose_resolved_plan_overdue。
    resolution = service.plan_query.resolve_plan_view(VERSION, plan_role, scenario_id)
    return service.diagnose_resolved_plan_overdue(
        version=VERSION,
        resolution=resolution,
        as_of_time=AS_OF_TIME,
    )


def test_delay_diagnosis_reports_overdue_clues_and_stays_readonly(tmp_path) -> None:
    conn, _scenario_id = _seed_db(tmp_path)
    try:
        before = _snapshot(conn)
        report = _diagnose_via_live_door(ScheduleDelayDiagnosisService(conn), plan_role=ROLE_ADOPTED)
        after = _snapshot(conn)

        assert after == before
        assert report.total_count == 2
        assert report.scheduled_count == 1
        assert report.unscheduled_count == 1
        assert report.plan_identity.requested_plan_role == ROLE_ADOPTED
        assert report.plan_identity.source_table == SOURCE_SCHEDULE
        assert report.trace_meta.rule_version == "delay-diagnosis-v1"
        assert report.trace_meta.evidence_count >= 1
        assert len(report.trace_meta.input_fingerprint) == 64
        assert any("没有现场执行反馈" in text for text in report.warnings)

        scheduled = _item_by_batch(report, "B_SCHEDULED")
        assert scheduled.bucket == "scheduled_overdue"
        assert scheduled.finish_time == "2026-05-04 11:00:00"
        assert scheduled.suggested_operation_clue is not None
        assert scheduled.suggested_operation_clue.op_id == 20
        assert scheduled.suggested_operation_clue.planned_end_time == "2026-05-04 11:00:00"
        assert {"material_not_ready", "material_status_missing", "downtime_impact", "suggested_operation_clue"} <= _clue_codes(scheduled)
        assert all(clue.evidences for clue in scheduled.candidate_clues)
        assert any(
            evidence.source_table == "schedule"
            and evidence.source_row_id == 120
            and evidence.evidence_scope == "row"
            for evidence in scheduled.evidences
        )
        material_evidence = [
            evidence for evidence in scheduled.evidences if evidence.source_table == "batch_materials"
        ]
        assert material_evidence
        assert material_evidence[0].metric_name == "material_readiness"
        assert set(material_evidence[0].metric_value) >= {"ready_status", "required_qty", "available_qty"}
        assert any(evidence.evidence_scope == "missing_data" for evidence in scheduled.evidences)
        assert "根因" not in str(scheduled.to_dict())
        assert "critical_chain" not in str(scheduled.to_dict())
        assert "primary_reason" not in str(scheduled.to_dict())
        rendered_links = "\n".join(str(evidence.link or "") for clue in scheduled.candidate_clues for evidence in clue.evidences)
        assert "/material/batches" in rendered_links
        assert "/reports/downtime" in rendered_links
        assert "/materials/batches" not in rendered_links
        assert "/reports/downtime-impact" not in rendered_links

        unscheduled = _item_by_batch(report, "B_UNSCHEDULED")
        assert unscheduled.bucket == "unscheduled_overdue"
        assert unscheduled.finish_time is None
        assert unscheduled.suggested_operation_clue is None
        assert unscheduled.leading_clue_code == "unscheduled"
        assert unscheduled.confidence == "missing_data"
        assert any("排程明细" in gap for gap in unscheduled.data_gaps)
        assert any(
            evidence.evidence_scope == "aggregate"
            and evidence.aggregation_key == "batch:B_UNSCHEDULED:overdue"
            for evidence in unscheduled.evidences
        )
        assert unscheduled.trace_meta.evidence_count == len(unscheduled.evidences)
        assert {"超期清单", "BatchMaterials"} <= set(unscheduled.trace_meta.evidence_sources)
    finally:
        conn.close()


def test_delay_diagnosis_reads_candidate_rows_without_fallback(tmp_path) -> None:
    conn, _scenario_id = _seed_db(tmp_path)
    try:
        service = ScheduleDelayDiagnosisService(conn)
        before = _snapshot(conn)
        report = _diagnose_via_live_door(service, plan_role=ROLE_BASELINE_BEST)
        after = _snapshot(conn)

        assert after == before
        assert report.plan_identity.requested_plan_role == ROLE_BASELINE_BEST
        assert report.plan_identity.source_table == SOURCE_CANDIDATE_ROWS
        item = _item_by_batch(report, "B_SCHEDULED")
        assert item.finish_time == "2026-05-04 14:00:00"
        assert all("plan_role=baseline_best" in (evidence.link or "") for evidence in item.evidences if evidence.link)

        conn.execute("DELETE FROM ScheduleCandidateRows")
        conn.commit()
        # O21 钉层（禁平移）：「候选缺明细必须 loud raise」的灵魂线钉在 resolve_existing_plan 层——
        # 活门非 scenario 走 resolve_plan 会 fallback_to_adopted 静默回退，平移到活门 diagnose 入口
        # 会让这条「无静默回退」覆盖被 fallback 吞掉（RK14）。
        with pytest.raises(ValueError, match="所选方案没有可查看的明细"):
            service.plan_query.resolve_existing_plan(VERSION, ROLE_BASELINE_BEST)
        # 「角色在册但明细被删」场景活门也 loud（_validate 文案「方案对比明细没有找到对应排程」），
        # 不是 fallback——把这点也钉死，防误以为活门对一切坏态都静默。
        with pytest.raises(ValueError, match="方案对比明细没有找到对应排程"):
            service.plan_query.resolve_plan_view(VERSION, ROLE_BASELINE_BEST, None)
        # 死/活差异显式钉死：「角色完全缺席」时活门非 scenario 路径静默回退 adopted 而非 raise
        # （死门 resolve_existing_plan 对同场景 raise「所选方案不存在」）——这是 resolve_plan 既有
        # 语义（独立隐患，另行裁决），本测试只把差异写明防误判两门等价。
        conn.execute("DELETE FROM ScheduleCandidateSelection")
        conn.execute("DELETE FROM ScheduleCandidate")
        conn.commit()
        fallback_resolution = service.plan_query.resolve_plan_view(VERSION, ROLE_BASELINE_BEST, None)
        assert fallback_resolution.status == "fallback_to_adopted"
        assert "已显示正式采用方案" in fallback_resolution.message
        with pytest.raises(ValueError, match="所选方案不存在"):
            service.plan_query.resolve_existing_plan(VERSION, ROLE_BASELINE_BEST)
    finally:
        conn.close()


def test_delay_diagnosis_reads_scenario_rows_without_fallback(tmp_path) -> None:
    conn, scenario_id = _seed_db(tmp_path)
    try:
        service = ScheduleDelayDiagnosisService(conn)
        before = _snapshot(conn)
        report = _diagnose_via_live_door(service, plan_role=ROLE_ADOPTED, scenario_id=scenario_id)
        after = _snapshot(conn)

        assert after == before
        assert report.plan_identity.source_table == "adjustment_scenario_rows"
        assert report.plan_identity.scenario_id == scenario_id
        assert report.plan_identity.is_preview is True
        assert report.plan_identity.can_write_feedback is False
        item = _item_by_batch(report, "B_SCHEDULED")
        assert item.finish_time == "2026-05-04 16:00:00"
        assert all(f"scenario_id={scenario_id}" in (evidence.link or "") for evidence in item.evidences if evidence.link)

        conn.execute("DELETE FROM ScheduleAdjustmentScenarioRow WHERE scenario_id = ?", (scenario_id,))
        conn.commit()
        # O22 平移：scenario 分支死/活两门同源（都经 resolve_plan_view→_resolve_scenario_plan），
        # 缺明细 raise 发生在 resolve 阶段，平移后断言生产现行的 resolve_plan_view 即覆盖活门全链。
        with pytest.raises(ValueError, match="模拟方案明细不存在"):
            service.plan_query.resolve_plan_view(VERSION, ROLE_ADOPTED, scenario_id)
    finally:
        conn.close()
