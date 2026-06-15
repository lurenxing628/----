"""回归测试：报表上下文资源筛选契约——filter_downtime_rows_for_report_context 与 normalize_report_resource_filter 对设备/人员/班组维度的筛选、缺编号、别名冲突的接受与拒绝规则，并经 /reports/utilization(/export) 路由、SchedulePlanQueryService/Repository 三层一致校验（不支持的维度不下探到 repo，明细 SQL 把 batch_id 与资源筛选下推到底层并参数化）。"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from core.infrastructure.errors import ValidationError
from core.models.schedule_plan_identity import PlanIdentity
from core.services.report.report_context_filters import (
    filter_downtime_rows_for_report_context,
    normalize_report_resource_filter,
)
from core.services.scheduler.schedule_delay_diagnosis_service import ScheduleDelayDiagnosisService
from core.services.scheduler.schedule_plan_query_service import SchedulePlanQueryService
from data.repositories.schedule_plan_query_repo import SchedulePlanQueryRepository
from tests.web_pages.reports_workbench_backlink_helpers import _client, _xlsx_text


def test_downtime_batch_filter_keeps_only_real_schedule_overlap() -> None:
    rows = [
        {"machine_id": "M1", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
        {"machine_id": "M2", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
        {"machine_id": "M3", "start_time": "bad", "end_time": "2026-05-01 09:00"},
    ]
    schedule_rows = [
        {"machine_id": "M1", "start_time": "2026-05-01 08:30", "end_time": "2026-05-01 10:00"},
        {"machine_id": "M2", "start_time": "2026-05-01 09:00", "end_time": "2026-05-01 10:00"},
        {"machine_id": "M3", "start_time": "2026-05-01 08:30", "end_time": "2026-05-01 10:00"},
    ]

    filtered = filter_downtime_rows_for_report_context(rows, schedule_rows, batch_id="B1")

    assert [row["machine_id"] for row in filtered] == ["M1"]


def test_downtime_machine_filter_without_batch_does_not_need_schedule_overlap() -> None:
    rows = [
        {"machine_id": "M1", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
        {"machine_id": "M2", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
    ]

    filtered = filter_downtime_rows_for_report_context(rows, [], resource_type="machine", resource_id="M2")

    assert [row["machine_id"] for row in filtered] == ["M2"]


def test_downtime_operator_filter_uses_schedule_machine_scope() -> None:
    rows = [
        {"machine_id": "M1", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
        {"machine_id": "M2", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"},
    ]
    schedule_rows = [{"machine_id": "M2", "operator_id": "O1"}]

    filtered = filter_downtime_rows_for_report_context(rows, schedule_rows, resource_type="operator", resource_id="O1")

    assert [row["machine_id"] for row in filtered] == ["M2"]


def test_downtime_operator_filter_empty_schedule_scope_returns_empty_rows() -> None:
    rows = [{"machine_id": "M1", "start_time": "2026-05-01 08:00", "end_time": "2026-05-01 09:00"}]

    filtered = filter_downtime_rows_for_report_context(rows, [], resource_type="operator", resource_id="O1")

    assert filtered == []


def test_report_core_filter_rejects_unsupported_resource_type() -> None:
    with pytest.raises(ValidationError, match="当前报表暂不支持班组维度筛选"):
        normalize_report_resource_filter(resource_type="team", resource_id="T-RPT")


def test_report_core_filter_rejects_resource_type_without_resource_id() -> None:
    with pytest.raises(ValidationError, match="缺少设备编号"):
        normalize_report_resource_filter(resource_type="machine")

    with pytest.raises(ValidationError, match="缺少人员编号"):
        normalize_report_resource_filter(resource_type="operator")


def test_report_core_filter_rejects_conflicting_resource_aliases() -> None:
    with pytest.raises(ValidationError, match="同时收到了人员编号"):
        normalize_report_resource_filter(resource_type="machine", resource_id="M-RPT", operator_id="O-RPT")

    with pytest.raises(ValidationError, match="设备编号冲突"):
        normalize_report_resource_filter(resource_type="machine", resource_id="M-RPT", machine_id="M-OTHER")

    with pytest.raises(ValidationError, match="资源筛选类型冲突"):
        normalize_report_resource_filter(
            resource_type="machine",
            resource_id="M-RPT",
            scope_type="operator",
            scope_id="M-RPT",
        )

    with pytest.raises(ValidationError, match="资源筛选编号冲突"):
        normalize_report_resource_filter(
            resource_type="machine",
            resource_id="M-RPT",
            scope_type="machine",
            scope_id="M-OTHER",
        )


def test_report_request_rejects_resource_type_without_resource_id() -> None:
    client = _client()

    page_response = client.get(
        "/reports/utilization?version=12&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06&resource_type=machine"
    )
    export_response = client.get(
        "/reports/utilization/export?version=12&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06&resource_type=machine"
    )

    assert page_response.status_code == 400
    assert export_response.status_code == 400
    assert "缺少设备编号" in page_response.get_data(as_text=True)
    assert "缺少设备编号" in export_response.get_data(as_text=True)


def test_report_request_rejects_conflicting_resource_aliases() -> None:
    client = _client()

    page_response = client.get(
        "/reports/utilization?version=12&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=machine&resource_id=M-RPT&operator_id=O-RPT"
    )
    export_response = client.get(
        "/reports/utilization/export?version=12&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06"
        "&resource_type=machine&resource_id=M-RPT&machine_id=M-OTHER"
    )

    assert page_response.status_code == 400
    assert export_response.status_code == 400
    assert "同时收到了人员编号" in page_response.get_data(as_text=True)
    assert "设备编号冲突" in export_response.get_data(as_text=True)


def test_report_request_infers_machine_resource_without_silent_broad_export() -> None:
    client = _client()
    response = client.get(
        "/reports/utilization/export?version=12&plan_role=adopted"
        "&start_date=2026-05-06&end_date=2026-05-06&machine_id=M-RPT"
    )

    assert response.status_code == 200
    export_text = _xlsx_text(response.data)
    assert "M-RPT" in export_text
    assert "M-OTHER" not in export_text


def test_overdue_query_service_rejects_unsupported_or_half_resource_filter() -> None:
    class _Repo:
        def list_overdue_base_rows(self, **_kwargs):
            raise AssertionError("资源筛选没通过 service 校验前，不应该下探到 repository。")

    service = SchedulePlanQueryService(None, repo=_Repo())  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match="超期查询只支持设备或人员维度"):
        service.list_plan_overdue_base_rows_for_resolution(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_type="team",
            resource_id="T-RPT",
        )
    with pytest.raises(ValidationError, match="超期查询缺少资源类型"):
        service.list_plan_overdue_base_rows_for_resolution(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_id="M-RPT",
        )
    with pytest.raises(ValidationError, match="超期查询缺少资源编号"):
        service.list_plan_overdue_base_rows_for_resolution(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_type="machine",
        )


def test_overdue_query_repository_rejects_unsupported_resource_filter_at_bottom() -> None:
    repo = SchedulePlanQueryRepository.__new__(SchedulePlanQueryRepository)

    with pytest.raises(ValidationError, match="超期查询只支持设备或人员维度"):
        repo.list_overdue_base_rows(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_type="team",
            resource_id="T-RPT",
        )
    with pytest.raises(ValidationError, match="超期查询缺少资源类型"):
        repo.list_overdue_base_rows(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_id="M-RPT",
        )
    with pytest.raises(ValidationError, match="超期查询缺少资源编号"):
        repo.list_overdue_base_rows(
            version=12,
            source_table="schedule",
            candidate_id=None,
            resource_type="machine",
        )


def test_plan_detail_repository_pushes_batch_and_resource_filters_to_bottom_sql() -> None:
    repo = SchedulePlanQueryRepository.__new__(SchedulePlanQueryRepository)
    captured = {}

    def fake_fetchall(sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return []

    repo.fetchall = fake_fetchall  # type: ignore[method-assign]
    repo.list_detail_rows_between(
        version=12,
        source_table="schedule",
        candidate_id=None,
        start_time="2026-05-06 00:00:00",
        end_time="2026-05-07 00:00:00",
        batch_id="B-RPT",
        resource_type="machine",
        resource_id="M-RPT",
    )

    assert "TRIM(CAST(bo.batch_id AS TEXT)) = ?" in captured["sql"]
    assert "TRIM(COALESCE(s.machine_id, '')) = ?" in captured["sql"]
    assert captured["params"][-2:] == ("B-RPT", "M-RPT")

    repo.list_detail_rows_all(
        version=12,
        source_table="schedule",
        candidate_id=None,
        batch_id="B-RPT",
        resource_type="operator",
        resource_id="O-RPT",
    )
    assert "TRIM(COALESCE(s.operator_id, '')) = ?" in captured["sql"]
    assert captured["params"][-2:] == ("B-RPT", "O-RPT")


def _diagnosis_plan_identity() -> PlanIdentity:
    return PlanIdentity(
        version=12,
        requested_plan_role="adopted",
        effective_plan_role="adopted",
        plan_resolution_status="resolved_adopted",
        source_table="schedule",
        source_row_id=None,
        candidate_id=None,
        candidate_key=None,
        scenario_id=None,
        schedule_result_status="success",
        result_summary_parse_failed=False,
        result_summary_parse_reason="",
        is_simulation=False,
        label="正式采用方案",
        user_label="正式采用方案",
        is_official=True,
        is_preview=False,
        is_current_executable_version=True,
        is_current_executable_official_version=True,
        is_superseded_by_newer_version=False,
        schedule_lock_status=None,
        can_dispatch=True,
        can_write_feedback=True,
        detail_saved=True,
    )


def test_delay_diagnosis_service_pushes_batch_and_resource_filters_to_plan_queries() -> None:
    calls = []

    class _PlanQuery:
        def list_plan_overdue_base_rows_for_resolution(self, **kwargs):
            calls.append(("overdue", kwargs))
            return []

        def list_plan_detail_rows_all_for_resolution(self, **kwargs):
            calls.append(("detail", kwargs))
            return []

    service = ScheduleDelayDiagnosisService.__new__(ScheduleDelayDiagnosisService)
    service.plan_query = _PlanQuery()
    service.clue_builder = SimpleNamespace()

    report = service.diagnose_resolved_plan_overdue(
        version=12,
        resolution=SimpleNamespace(
            source_table="schedule",
            candidate_id=None,
            scenario_id=None,
            plan_identity=_diagnosis_plan_identity(),
        ),
        resource_type="machine",
        resource_id="M-RPT",
        batch_id="B-RPT",
    )

    assert report.total_count == 0
    assert calls == [
        (
            "overdue",
            {
                "version": 12,
                "source_table": "schedule",
                "candidate_id": None,
                "scenario_id": None,
                "resource_type": "machine",
                "resource_id": "M-RPT",
                "batch_id": "B-RPT",
            },
        ),
        (
            "detail",
            {
                "version": 12,
                "source_table": "schedule",
                "candidate_id": None,
                "scenario_id": None,
                "resource_type": "machine",
                "resource_id": "M-RPT",
                "batch_id": "B-RPT",
            },
        ),
    ]


def test_report_resource_filter_arg_keys_match_normalizer_signature() -> None:
    # R67 收口契约:常量是 web 侧抄键的单一来源,必须与 normalize_report_resource_filter
    # 的 6 个参数名按签名序逐一对应——签名加参/改名而忘改常量(或反之)在此红灯。
    import inspect

    from core.services.report.report_context_filters import (
        REPORT_RESOURCE_FILTER_ARG_KEYS,
        normalize_report_resource_filter,
    )

    assert REPORT_RESOURCE_FILTER_ARG_KEYS == (
        "resource_type",
        "resource_id",
        "scope_type",
        "scope_id",
        "machine_id",
        "operator_id",
    )
    signature_params = tuple(inspect.signature(normalize_report_resource_filter).parameters)
    assert signature_params == REPORT_RESOURCE_FILTER_ARG_KEYS
