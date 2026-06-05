from __future__ import annotations

import pytest

from core.models.schedule_plan_identity import EvidenceLink
from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, SchedulePlanQueryService
from data.repositories.schedule_plan_query_repo import SOURCE_SCHEDULE
from tests.regression_scheduler_plan_identity_evidence_contract import VERSION, _seed_db


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
