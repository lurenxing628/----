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

    gantt = build_workbench_link(context, "gantt", label="查看设备甘特", view="machine")
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
        "batch_id=B202605-001",
        "view=machine",
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
        "batch_id",
        "resource_type",
        "resource_id",
    ]

    for fragment in (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=week",
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
    assert "scope_type=operator" in utilization["url"]
    assert "张三" in utilization["context_summary"]

    assert "version=12" in review["url"]
    assert "plan_role=adopted" in review["url"]
    assert "date_from=2026-05-25" in review["url"]
    assert "date_to=2026-05-31" in review["url"]
    assert "query_date=2026-05-28" in review["url"]
    assert "period_preset=week" in review["url"]
    assert "batch_id=B202605-001" in review["url"]
    assert "scope_type=operator" in review["url"]
    assert "scope_id=O1" in review["url"]


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
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
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
            "period_preset": "week",
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
            "scope_type": "machine",
            "scope_id": "M1",
            "machine_id": "M1",
        },
        "execution_review": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "scope_type": "machine",
            "scope_id": "M1",
            "machine_id": "M1",
        },
        "reports_index": {
            "version": "12",
            "plan_role": "adopted",
            "date_from": "2026-05-25",
            "date_to": "2026-05-31",
            "query_date": "2026-05-28",
            "period_preset": "week",
            "batch_id": "B202605-001",
            "scope_type": "machine",
            "scope_id": "M1",
            "machine_id": "M1",
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
    assert "scope_type=machine" in reports["url"]
    assert "scope_id=M1" in reports["url"]
    assert "machine_id=M1" in reports["url"]
    assert "period_preset=week" not in dispatch["url"]
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
        "reports_index",
    }
    assert plan_role_label("baseline_best") == "原算法代表方案"
    assert guardrail_reason_label("data_gap") == "数据不足，暂时不能判断"
    assert resource_type_label("machine") == "设备视角"
    assert period_preset_label("custom") == "自定义"
    assert gantt_view_label("operator") == "人员甘特"


def test_feedback_write_url_guardrail_is_explicit() -> None:
    assert can_emit_feedback_write_urls({"plan_role": "adopted", "can_dispatch": True, "can_write_feedback": True}) is True
    assert can_emit_feedback_write_urls({"plan_role": "adopted", "can_dispatch": True, "can_write_feedback": False}) is False
    assert can_emit_feedback_write_urls({"plan_role": "adopted", "can_dispatch": False, "can_write_feedback": True}) is False
    assert can_emit_feedback_write_urls({"can_write_feedback": True}) is False
    assert can_emit_feedback_write_urls({"plan_role": "adopted", "can_write_feedback": True}) is True
    assert can_emit_feedback_write_urls(
        {"plan_role": "adopted", "effective_plan_role": "baseline_best", "can_write_feedback": True}
    ) is False
    assert can_emit_feedback_write_urls(
        {"requested_plan_role": "adopted", "effective_plan_role": "baseline_best", "can_write_feedback": True}
    ) is False
    assert can_emit_feedback_write_urls(
        {"plan_role": "adopted", "requested_plan_role": "baseline_best", "can_write_feedback": True}
    ) is False
    assert can_emit_feedback_write_urls({"plan_role": "baseline_best", "can_write_feedback": True}) is False
    assert can_emit_feedback_write_urls({"scenario_id": "preview-1", "can_write_feedback": True}) is False

    read_only_context = build_workbench_plan_context(plan_role="baseline_best", can_write_feedback=True)
    assert read_only_context["can_write_feedback"] is False
    assert "只能查看" in read_only_context["guardrail_text"]

    implicit_context = build_workbench_plan_context(plan_role="adopted")
    assert implicit_context["can_write_feedback"] is False


def test_reports_index_requires_version_context() -> None:
    context = build_workbench_plan_context(plan_role="adopted")
    reports = build_workbench_link(context, "reports_index")

    assert reports["disabled"] is True
    assert reports["url"] == ""
    assert "还没有排产版本" in reports["disabled_reason"]


def test_workbench_view_links_require_date_range() -> None:
    context = build_workbench_plan_context(version=12, plan_role="adopted")

    for target_page in ("gantt", "week_plan", "resource_dispatch", "reports_index"):
        link = build_workbench_link(context, target_page)
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "日期范围" in link["disabled_reason"]


def test_manual_disabled_link_requires_public_reason() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=True,
    )
    link = build_workbench_link(context, "analysis", disabled=True)

    assert link["disabled"] is True
    assert link["url"] == ""
    assert "暂时不可用" in link["disabled_reason"]


def test_execution_review_guardrail_cannot_be_overridden_by_enabled_flag() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="baseline_best",
        date_from="2026-05-25",
        date_to="2026-05-31",
    )

    direct = build_workbench_link(context, "execution_review", disabled=False)
    from_specs = build_workbench_links(
        context,
        [
            {
                "target_page": "execution_review",
                "disabled": False,
            }
        ],
    )[0]

    for link in (direct, from_specs):
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]


def test_execution_review_guardrail_uses_full_plan_identity() -> None:
    base = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=True,
    )
    conflict_contexts = [
        dict(base, effective_plan_role="baseline_best"),
        dict(base, requested_plan_role="baseline_best"),
        dict(base, is_scenario_preview=True),
        dict(base, is_superseded_by_newer_version=True),
        dict(base, is_comparison=True),
    ]

    for context in conflict_contexts:
        link = build_workbench_link(context, "execution_review")
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]


def test_execution_review_allows_read_only_formal_adopted_context() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )
    context["can_dispatch"] = False

    link = build_workbench_link(context, "execution_review")

    assert link["disabled"] is False
    assert "plan_role=adopted" in link["url"]
    assert "scenario_id" not in _query_values(link["url"])
    assert context["can_write_feedback"] is False


def test_execution_review_rejects_scenario_identity_from_extra_params() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=True,
    )

    forbidden_keys = ("scenario_id", "plan_role", "is_comparison", "can_write_feedback")
    for key in forbidden_keys:
        try:
            build_workbench_link(context, "execution_review", extra_params={key: "leaked"})
        except ValueError as exc:
            assert "extra_params" in str(exc)
        else:
            raise AssertionError(f"计划和现场实际入口不能允许 extra_params 追加 {key}")


def test_workbench_link_specs_fail_loudly_when_target_is_missing() -> None:
    context = build_workbench_plan_context(version=12, plan_role="adopted")

    try:
        build_workbench_links(context, [{"label": "缺目标页"}])
    except ValueError as exc:
        assert "target_page" in str(exc)
    else:
        raise AssertionError("缺少 target_page 的工作台链接配置必须报错")

    try:
        build_workbench_links(context, ["not-a-spec"])  # type: ignore[list-item]
    except ValueError as exc:
        assert "必须是字典" in str(exc)
    else:
        raise AssertionError("非字典工作台链接配置必须报错")
