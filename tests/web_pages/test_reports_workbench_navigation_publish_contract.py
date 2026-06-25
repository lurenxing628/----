"""回归测试：排产页发布导航上下文时保留方案身份、资源筛选和护栏字段。"""

from __future__ import annotations

from tests.web_pages.reports_workbench_backlink_helpers import _client, _query


def test_scheduler_navigation_publish_keeps_plan_guard_fields() -> None:
    app = _client().application
    from web.navigation_context import build_report_navigation_links, current_workbench_navigation_context
    from web.routes.domains.scheduler.scheduler_navigation_publish import (
        publish_analysis_navigation_context,
        publish_gantt_navigation_context,
        publish_week_plan_navigation_context,
    )

    superseded_plan = dict(
        requested_role="adopted", selected_role="adopted",
        is_scenario_preview=False, is_comparison=False, is_official=True, is_preview=False,
        is_superseded_by_newer_version=True, is_current_executable_official_version=False,
        can_dispatch=True, can_write_feedback=True,
    )
    expected_guard_fields = dict(
        requested_plan_role="adopted", effective_plan_role="adopted",
        plan_role_status="resolved_adopted", is_scenario_preview=False, is_comparison=False,
        is_superseded_by_newer_version=True, is_official_plan=True, is_preview_plan=False,
        is_current_executable_official_version=False, can_dispatch=True, can_write_feedback=True,
    )

    with app.test_request_context("/scheduler/analysis"):
        context = publish_analysis_navigation_context(
            version=12,
            plan_resolution=superseded_plan,
            date_from="2026-05-06",
            date_to="2026-05-07",
            resource_context={},
        )
        links = {item["label"]: item for item in build_report_navigation_links()}

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields
        assert links["计划和现场实际"]["disabled"] is True
        assert links["计划和现场实际"]["url"] == ""
        assert "历史正式方案" in links["计划和现场实际"]["disabled_reason"]

    with app.test_request_context("/scheduler/gantt"):
        context = publish_gantt_navigation_context(
            version=12,
            plan_resolution=dict(superseded_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            view="machine",
            gantt_resource="M-RPT",
        )

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields
        assert current_workbench_navigation_context()["resource_type"] == "machine"
        assert current_workbench_navigation_context()["resource_id"] == "M-RPT"

    with app.test_request_context("/scheduler/week-plan"):
        context = publish_week_plan_navigation_context(
            version=12,
            plan_resolution=dict(superseded_plan),
            fallback_scenario_id=None,
            date_from="2026-05-06",
            date_to="2026-05-07",
        )

        current_context = current_workbench_navigation_context()
        assert {key: current_context[key] for key in expected_guard_fields} == expected_guard_fields
        assert {key: context[key] for key in expected_guard_fields} == expected_guard_fields


def test_scheduler_navigation_publish_accepts_navigation_context_plan_role_shape() -> None:
    app = _client().application
    from web.navigation_context import (
        build_report_navigation_links,
        build_scheduler_navigation_links,
        current_workbench_navigation_context,
    )
    from web.routes.domains.scheduler.scheduler_navigation_publish import (
        publish_analysis_navigation_context,
        publish_gantt_navigation_context,
        publish_week_plan_navigation_context,
    )
    from web.routes.domains.scheduler.scheduler_week_plan_query import week_plan_export_url

    navigation_shape_plan = dict(
        requested_plan_role="baseline_best",
        effective_plan_role="baseline_best",
        plan_role_status="resolved_candidate",
        can_dispatch=False,
        can_write_feedback=False,
    )

    with app.test_request_context("/scheduler/analysis"):
        publish_analysis_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            resource_context={},
        )
        current_context = current_workbench_navigation_context()
        report_links = {item["label"]: item for item in build_report_navigation_links()}

        assert current_context["plan_role"] == "baseline_best"
        assert current_context["requested_plan_role"] == "baseline_best"
        assert _query(report_links["超期清单"]["url"])["plan_role"] == ["baseline_best"]

    with app.test_request_context("/scheduler/gantt"):
        publish_gantt_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            date_from="2026-05-06",
            date_to="2026-05-07",
            view="machine",
            gantt_resource="M-RPT",
        )
        current_context = current_workbench_navigation_context()
        scheduler_links = {item["label"]: item for item in build_scheduler_navigation_links()}

        assert current_context["plan_role"] == "baseline_best"
        assert _query(scheduler_links["排产优化分析"]["url"])["plan_role"] == ["baseline_best"]

    with app.test_request_context("/scheduler/week-plan"):
        publish_week_plan_navigation_context(
            version=12,
            plan_resolution=dict(navigation_shape_plan),
            fallback_scenario_id=None,
            date_from="2026-05-06",
            date_to="2026-05-07",
        )
        current_context = current_workbench_navigation_context()
        export_url = week_plan_export_url(
            version=12,
            week_start="2026-05-06",
            plan_resolution=dict(navigation_shape_plan),
        )

        assert current_context["plan_role"] == "baseline_best"
        assert export_url is not None
        assert _query(export_url)["plan_role"] == ["baseline_best"]


def test_scheduler_pages_selected_plan_role_use_core_contract() -> None:
    from core.services.scheduler.schedule_result_view_context import selected_plan_role as core_selected_plan_role
    from web.routes.domains.scheduler.scheduler_gantt import selected_plan_role as gantt_selected_plan_role
    from web.routes.domains.scheduler.scheduler_week_plan import selected_plan_role as week_selected_plan_role

    for plan_resolution in (
        {"selected_role": "baseline_best"},
        {"selected_role": None},
        {"selected_role": ""},
        {},
        None,
    ):
        assert gantt_selected_plan_role(plan_resolution) == core_selected_plan_role(plan_resolution)
        assert week_selected_plan_role(plan_resolution) == core_selected_plan_role(plan_resolution)


def test_scheduler_navigation_rejects_conflicting_resource_aliases() -> None:
    client = _client()

    response = client.get(
        "/scheduler/gantt?view=machine&version=12&start_date=2026-05-06&end_date=2026-05-06"
        "&machine_id=M-RPT&operator_id=O-RPT"
    )

    assert response.status_code == 400
    assert "资源筛选同时包含设备和人员" in response.get_data(as_text=True)


def test_week_plan_rejects_scope_type_without_scope_id() -> None:
    client = _client()

    for path in ("/scheduler/week-plan", "/scheduler/week-plan/export"):
        response = client.get(f"{path}?version=12&week_start=2026-05-06&scope_type=machine")
        assert response.status_code == 400
        assert "资源筛选类型是设备，但缺少设备编号" in response.get_data(as_text=True)
