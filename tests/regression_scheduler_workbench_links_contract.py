from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from web.viewmodels.scheduler_workbench_links import (
    TARGET_PAGE_PATHS,
    build_workbench_link,
    build_workbench_links,
    build_workbench_plan_context,
    can_emit_feedback_write_urls,
    gantt_view_label,
    guardrail_reason_label,
    period_preset_label,
    plan_role_label,
    resource_type_label,
)


def _query_values(url: str) -> dict:
    return {key: values[-1] for key, values in parse_qs(urlparse(url).query).items()}


def test_workbench_context_and_link_keep_plan_date_and_resource_params() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        period_preset="week",
        batch_id="B202605-001",
        resource_type="operator",
        resource_id="O1",
        resource_label="张三",
        can_write_feedback=True,
    )

    gantt = build_workbench_link(context, "gantt", label="查看人员甘特", view="operator")
    dispatch = build_workbench_link(context, "resource_dispatch", label="查看排班")
    week_plan = build_workbench_link(context, "week_plan", label="查看周计划")
    utilization = build_workbench_link(context, "utilization_report", label="看资源负荷")
    review = build_workbench_link(context, "execution_review", label="查看计划和实际")

    assert gantt["target_page"] == "gantt"
    assert gantt["disabled"] is False
    assert "/scheduler/gantt?" in gantt["url"]
    for fragment in (
        "version=12",
        "plan_role=adopted",
        "start_date=2026-05-25",
        "end_date=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=week",
        "gantt_batch=B202605-001",
        "gantt_resource=O1",
        "view=operator",
    ):
        assert fragment in gantt["url"]
    assert gantt["required_params"] == [
        "view",
        "version",
        "plan_role",
        "start_date",
        "end_date",
        "query_date",
        "period_preset",
        "gantt_batch",
        "gantt_resource",
    ]

    for fragment in (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=custom",
        "scope_type=operator",
        "operator_id=O1",
        "batch_id=B202605-001",
    ):
        assert fragment in dispatch["url"]
    assert "start_date=" not in dispatch["url"]
    assert "end_date=" not in dispatch["url"]
    assert "query_date" in dispatch["required_params"]
    assert "period_preset" in dispatch["required_params"]
    assert "scope_type" in dispatch["required_params"]

    assert "/scheduler/week-plan?" in week_plan["url"]
    assert "version=12" in week_plan["url"]
    assert "plan_role=adopted" in week_plan["url"]
    assert "week_start=2026-05-25" in week_plan["url"]
    assert "date_from=2026-05-25" in week_plan["url"]
    assert "date_to=2026-05-31" in week_plan["url"]
    assert "query_date=2026-05-28" in week_plan["url"]
    assert "period_preset=week" in week_plan["url"]
    assert "batch_id=B202605-001" in week_plan["url"]
    assert "resource_type=operator" in week_plan["url"]
    assert "resource_id=O1" in week_plan["url"]
    assert week_plan["required_params"] == [
        "version",
        "plan_role",
        "week_start",
        "date_from",
        "date_to",
        "query_date",
        "period_preset",
        "batch_id",
        "resource_type",
        "resource_id",
    ]

    assert "start_date=2026-05-25" in utilization["url"]
    assert "batch_id=B202605-001" in utilization["url"]
    assert "resource_type=operator" in utilization["url"]
    assert "resource_id=O1" in utilization["url"]
    assert "张三" in utilization["context_summary"]

    assert "version=12" in review["url"]
    assert "plan_role=adopted" in review["url"]
    assert "date_from=2026-05-25" in review["url"]
    assert "date_to=2026-05-31" in review["url"]
    assert "query_date=2026-05-28" in review["url"]
    assert "period_preset=week" in review["url"]
    assert "batch_id=B202605-001" in review["url"]
    assert "resource_type=operator" in review["url"]
    assert "resource_id=O1" in review["url"]


def test_all_target_pages_preserve_full_workbench_context_matrix() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        period_preset="week",
        batch_id="B202605-001",
        resource_type="machine",
        resource_id="M1",
        resource_label="M1 号设备",
        can_write_feedback=True,
    )
    expected_by_target = {
        "dashboard": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "analysis": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "gantt": {
            "view": "machine",
            "version": "12",
            "plan_role": "adopted",
            "start_date": "2026-05-25",
            "end_date": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "gantt_batch": "B202605-001",
            "gantt_resource": "M1",
        },
        "week_plan": {
            "version": "12",
            "plan_role": "adopted",
            "week_start": "2026-05-25",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "resource_dispatch": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "custom",
            "batch_id": "B202605-001",
            "scope_type": "machine",
            "scope_id": "M1",
            "machine_id": "M1",
        },
        "overdue_report": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "delay_diagnosis": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "utilization_report": {
            "version": "12",
            "plan_role": "adopted",
            "start_date": "2026-05-25",
            "end_date": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "downtime_report": {
            "version": "12",
            "plan_role": "adopted",
            "start_date": "2026-05-25",
            "end_date": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "execution_review": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "reports_index": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
    }

    for target_page, expected_query in expected_by_target.items():
        link = build_workbench_link(context, target_page, view="machine")

        assert link["disabled"] is False, target_page
        query = _query_values(link["url"])
        for key, value in expected_query.items():
            assert query.get(key) == value, (target_page, key, link["url"])
        for key in expected_query:
            assert key in link["required_params"], (target_page, key, link["required_params"])


def test_preview_context_keeps_view_links_but_disables_execution_review() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="baseline_best",
        scenario_id="scenario-secret",
        scenario_display_label="模拟方案甲",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )

    overdue = build_workbench_link(context, "overdue_report", label="看晚交")
    review = build_workbench_link(context, "execution_review")

    assert "scenario_id=scenario-secret" in overdue["url"]
    assert "plan_role=baseline_best" in overdue["url"]
    assert overdue["context_summary"].startswith("v12，模拟方案甲")
    assert review["disabled"] is True
    assert review["url"] == ""
    assert "只复盘正式采用方案" in review["disabled_reason"]
    assert "scenario_id" not in review["required_params"]


def test_primary_resource_links_disable_unsupported_team_context() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        period_preset="week",
        resource_type="team",
        resource_id="T1",
        can_write_feedback=True,
    )

    for target_page in (
        "dashboard",
        "analysis",
        "week_plan",
        "reports_index",
        "overdue_report",
        "delay_diagnosis",
        "utilization_report",
        "execution_review",
        "downtime_report",
    ):
        link = build_workbench_link(context, target_page)

        assert link["disabled"] is True, target_page
        assert link["url"] == ""
        assert "当前页面暂不支持班组维度筛选" in link["disabled_reason"]

    dispatch = build_workbench_link(context, "resource_dispatch")
    assert dispatch["disabled"] is False
    assert "scope_type=team" in dispatch["url"]
    assert "scope_id=T1" in dispatch["url"]
    assert "team_id=T1" in dispatch["url"]
    assert "resource_type=team" not in dispatch["url"]

    gantt = build_workbench_link(context, "gantt", view="machine")
    assert gantt["disabled"] is False
    assert "resource_type=team" not in gantt["url"]
    assert "resource_id=T1" not in gantt["url"]
    assert "team_id=T1" not in gantt["url"]
    assert "gantt_resource=T1" not in gantt["url"]


def test_dashboard_analysis_and_reports_links_keep_context_without_inventing_period() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        resource_type="machine",
        resource_id="M1",
        resource_label="M1 号设备",
    )

    dashboard = build_workbench_link(context, "dashboard")
    analysis = build_workbench_link(context, "analysis")
    reports = build_workbench_link(context, "reports_index")
    dispatch = build_workbench_link(context, "resource_dispatch")
    overdue = build_workbench_link(context, "overdue_report")
    delay = build_workbench_link(context, "delay_diagnosis", batch_id="B202605-001")

    for link in (dashboard, analysis, reports):
        assert "version=12" in link["url"]
        assert "plan_role=adopted" in link["url"]
        assert "date_from=2026-05-25" in link["url"]
        assert "date_to=2026-05-31" in link["url"]
        assert "query_date=2026-05-28" in link["url"]

    assert "resource_type=machine" in dashboard["url"]
    assert "resource_id=M1" in dashboard["url"]
    assert "resource_type=machine" in analysis["url"]
    assert "resource_id=M1" in analysis["url"]
    assert "query_date=2026-05-28" in reports["url"]
    assert "resource_type=machine" in reports["url"]
    assert "resource_id=M1" in reports["url"]
    assert "period_preset=custom" in dispatch["url"]
    assert "query_date=2026-05-28" in dispatch["url"]
    assert "scope_type=machine" in dispatch["url"]
    assert "machine_id=M1" in dispatch["url"]
    assert "date_from=2026-05-25" in overdue["url"]
    assert "date_to=2026-05-31" in overdue["url"]
    assert "query_date=2026-05-28" in overdue["url"]
    assert "resource_type=machine" in overdue["url"]
    assert "resource_id=M1" in overdue["url"]
    assert overdue["target_page"] == "overdue_report"

    assert delay["target_page"] == "delay_diagnosis"
    assert "/reports/overdue?" in delay["url"]
    assert "plan_role=adopted" in delay["url"]
    assert "date_from=2026-05-25" in delay["url"]
    assert "date_to=2026-05-31" in delay["url"]
    assert "query_date=2026-05-28" in delay["url"]
    assert "batch_id=B202605-001" in delay["url"]
    assert "resource_type=machine" in delay["url"]
    assert "resource_id=M1" in delay["url"]
    assert delay["label"] == "查看延期说明"


def test_target_pages_and_public_label_mappings_are_fixed() -> None:
    assert set(TARGET_PAGE_PATHS) == {
        "dashboard",
        "analysis",
        "gantt",
        "week_plan",
        "resource_dispatch",
        "overdue_report",
        "delay_diagnosis",
        "utilization_report",
        "execution_review",
        "downtime_report",
        "reports_index",
    }
    assert plan_role_label("baseline_best") == "原算法代表方案"
    assert guardrail_reason_label("data_gap") == "数据不足，暂时不能判断"
    assert resource_type_label("machine") == "设备视角"
    assert period_preset_label("custom") == "自定义"
    assert gantt_view_label("operator") == "人员甘特"
