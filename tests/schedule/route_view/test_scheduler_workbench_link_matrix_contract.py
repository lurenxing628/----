"""契约测试：scheduler_workbench_links 工作台跳转链接的构造与护栏——各目标页 URL 保真透传版本/方案身份/日期范围/批次/资源等参数及 required_params 顺序、标签映射固定；护栏侧逐键四态拦放（R54 parity oracle）：预览/对比/历史方案禁开复盘入口、班组维度不支持页禁用、缺版本或日期范围禁用、反馈写入按完整方案身份判定、execution_review 拒绝从 extra_params 注入身份、坏摘要与缺目标页配置一律响亮报错。"""

from __future__ import annotations

from typing import Tuple
from urllib.parse import parse_qs, urlparse

from flask import Flask

from core.models.schedule_plan_role import SOURCE_SCHEDULE
from web.viewmodels.scheduler_workbench_links import (
    FULL_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_plan_context,
)


def _query_values(url: str) -> dict:
    return {key: values[-1] for key, values in parse_qs(urlparse(url).query).items()}


# ===========================================================================
# 链接构造正向契约区（原 regression_scheduler_workbench_links_contract.py，6 函数）
# 正向 URL 参数保真矩阵：page → query 片段 / required_params 顺序 / 标签映射。
# ===========================================================================


def _operator_context() -> dict:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        plan_resolution={
            "requested_role": "adopted",
            "selected_role": "adopted",
            "source_table": SOURCE_SCHEDULE,
            "plan_identity": {
                "is_official": True,
                "is_preview": False,
                "is_simulation": False,
                "result_summary_parse_failed": False,
                "schedule_result_status": "success",
                "detail_saved": True,
                "is_current_executable_official_version": True,
                "can_dispatch": True,
                "can_write_feedback": True,
            },
        },
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
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
    return context


def _assert_url_fragments(url: str, fragments: Tuple[str, ...]) -> None:
    for fragment in fragments:
        assert fragment in url


def _assert_gantt_link(gantt: dict) -> None:
    assert gantt["target_page"] == "gantt"
    assert gantt["disabled"] is False
    assert "/scheduler/gantt?" in gantt["url"]
    _assert_url_fragments(gantt["url"], (
        "version=12",
        "plan_role=adopted",
        "start_date=2026-05-25",
        "end_date=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=week",
        "gantt_batch=B202605-001",
        "gantt_resource=O1",
        "view=operator",
    ))
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


def _assert_dispatch_link(dispatch: dict) -> None:
    _assert_url_fragments(dispatch["url"], (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=custom",
        "scope_type=operator",
        "operator_id=O1",
        "batch_id=B202605-001",
    ))
    assert "start_date=" not in dispatch["url"]
    assert "end_date=" not in dispatch["url"]
    assert "query_date" in dispatch["required_params"]
    assert "period_preset" in dispatch["required_params"]
    assert "scope_type" in dispatch["required_params"]


def _assert_week_plan_link(week_plan: dict) -> None:
    assert "/scheduler/week-plan?" in week_plan["url"]
    _assert_url_fragments(week_plan["url"], (
        "version=12",
        "plan_role=adopted",
        "week_start=2026-05-25",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=week",
        "batch_id=B202605-001",
        "resource_type=operator",
        "resource_id=O1",
    ))
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


def _assert_utilization_link(utilization: dict) -> None:
    _assert_url_fragments(utilization["url"], (
        "start_date=2026-05-25",
        "batch_id=B202605-001",
        "resource_type=operator",
        "resource_id=O1",
    ))
    assert "张三" in utilization["context_summary"]


def _assert_execution_review_link(review: dict) -> None:
    _assert_url_fragments(review["url"], (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "period_preset=week",
        "batch_id=B202605-001",
        "resource_type=operator",
        "resource_id=O1",
    ))


def test_workbench_context_and_link_keep_plan_date_and_resource_params() -> None:
    context = _operator_context()

    _assert_gantt_link(build_workbench_link(context, "gantt", label="查看人员甘特", view="operator"))
    _assert_dispatch_link(build_workbench_link(context, "resource_dispatch", label="查看排班"))
    _assert_week_plan_link(build_workbench_link(context, "week_plan", label="查看周计划"))
    _assert_utilization_link(build_workbench_link(context, "utilization_report", label="看资源负荷"))
    _assert_execution_review_link(build_workbench_link(context, "execution_review", label="查看计划和实际"))


def test_all_target_pages_preserve_full_workbench_context_matrix() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        plan_resolution={
            "requested_role": "adopted",
            "selected_role": "adopted",
            "source_table": SOURCE_SCHEDULE,
            "plan_identity": {
                "is_official": True,
                "is_preview": False,
                "is_simulation": False,
                "result_summary_parse_failed": False,
                "schedule_result_status": "success",
                "detail_saved": True,
                "is_current_executable_official_version": True,
                "can_dispatch": True,
                "can_write_feedback": True,
            },
        },
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
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
    context["is_current_executable_official_version"] = True
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
            "batch_id": "B202605-001",
            "resource_type": "machine",
            "resource_id": "M1",
        },
        "delay_diagnosis": {
            "version": "12",
            "plan_role": "adopted",
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
    app = Flask(__name__)
    with app.app_context():
        context = build_workbench_plan_context(
            version=12,
            plan_role="baseline_best",
            scenario_id="scenario-secret",
            plan_context_token="opaque-public-token",
            scenario_display_label="模拟方案甲",
            date_from="2026-05-25",
            date_to="2026-05-31",
            can_write_feedback=False,
        )

        overdue = build_workbench_link(context, "overdue_report", label="看晚交")
        review = build_workbench_link(context, "execution_review")

    query = _query_values(overdue["url"])
    assert "scenario_id" not in query
    assert query["plan_context_token"] == "opaque-public-token"
    assert "scenario-secret" not in overdue["url"]
    assert "plan_role=baseline_best" in overdue["url"]
    assert overdue["context_summary"].startswith("v12，模拟方案甲")
    assert review["disabled"] is True
    assert review["url"] == ""
    assert "只复盘正式采用方案" in review["disabled_reason"]
    assert "scenario_id" not in review["required_params"]


def test_preview_context_without_public_token_source_disables_public_link() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        scenario_id="scenario-secret",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )

    link = build_workbench_link(context, "resource_dispatch")

    assert link["disabled"] is True
    assert link["url"] == ""
    assert "刷新页面" in link["disabled_reason"]


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
