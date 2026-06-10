"""契约测试：scheduler_workbench_links 工作台跳转链接的构造与护栏——各目标页 URL 保真透传版本/方案身份/日期范围/批次/资源等参数及 required_params 顺序、标签映射固定；护栏侧逐键四态拦放（R54 parity oracle）：预览/对比/历史方案禁开复盘入口、班组维度不支持页禁用、缺版本或日期范围禁用、反馈写入按完整方案身份判定、execution_review 拒绝从 extra_params 注入身份、坏摘要与缺目标页配置一律响亮报错。"""

from __future__ import annotations

from typing import Tuple
from urllib.parse import parse_qs, urlparse

from core.models.schedule_plan_role import PLAN_ROLE_LABELS, SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from core.services.scheduler.schedule_result_view_context import plan_role_filter_fields
from web.viewmodels.scheduler_workbench_link_query import plan_guard_fields_for_resolution
from web.viewmodels.scheduler_workbench_links import (
    FULL_PLAN_GUARD_FIELDS,
    REPORT_PLAN_GUARD_FIELDS,
    RESOURCE_PLAN_GUARD_FIELDS,
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


# ===========================================================================
# 链接构造正向契约区（原 regression_scheduler_workbench_links_contract.py，6 函数）
# 正向 URL 参数保真矩阵：page → query 片段 / required_params 顺序 / 标签映射。
# ===========================================================================


def _operator_context() -> dict:
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
    context["is_current_executable_official_version"] = True
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
    context = _machine_context_without_period()

    dashboard = build_workbench_link(context, "dashboard")
    analysis = build_workbench_link(context, "analysis")
    reports = build_workbench_link(context, "reports_index")
    dispatch = build_workbench_link(context, "resource_dispatch")
    overdue = build_workbench_link(context, "overdue_report")
    delay = build_workbench_link(context, "delay_diagnosis", batch_id="B202605-001")

    _assert_dashboard_analysis_reports_context(dashboard, analysis, reports)
    _assert_dispatch_and_overdue_context(dispatch, overdue)
    _assert_delay_context(delay)


def _machine_context_without_period() -> dict:
    return build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        query_date="2026-05-28",
        resource_type="machine",
        resource_id="M1",
        resource_label="M1 号设备",
    )


def _assert_shared_context_fragments(link: dict) -> None:
    _assert_url_fragments(link["url"], (
        "version=12",
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
    ))


def _assert_dashboard_analysis_reports_context(dashboard: dict, analysis: dict, reports: dict) -> None:
    for link in (dashboard, analysis, reports):
        _assert_shared_context_fragments(link)

    _assert_url_fragments(dashboard["url"], ("resource_type=machine", "resource_id=M1"))
    _assert_url_fragments(analysis["url"], ("resource_type=machine", "resource_id=M1"))
    _assert_url_fragments(reports["url"], ("resource_type=machine", "resource_id=M1"))


def _assert_dispatch_and_overdue_context(dispatch: dict, overdue: dict) -> None:
    _assert_url_fragments(dispatch["url"], (
        "period_preset=custom",
        "query_date=2026-05-28",
        "scope_type=machine",
        "machine_id=M1",
    ))
    _assert_shared_context_fragments(overdue)
    _assert_url_fragments(overdue["url"], ("resource_type=machine", "resource_id=M1"))
    assert overdue["target_page"] == "overdue_report"


def _assert_delay_context(delay: dict) -> None:
    assert delay["target_page"] == "delay_diagnosis"
    assert "/reports/overdue?" in delay["url"]
    _assert_url_fragments(delay["url"], (
        "plan_role=adopted",
        "date_from=2026-05-25",
        "date_to=2026-05-31",
        "query_date=2026-05-28",
        "batch_id=B202605-001",
        "resource_type=machine",
        "resource_id=M1",
    ))
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
    assert plan_role_label("future_role") == "未知方案身份"
    assert guardrail_reason_label("data_gap") == "数据不足，暂时不能判断"
    assert guardrail_reason_label("future_reason") == "未知限制原因"
    assert resource_type_label("machine") == "设备视角"
    assert resource_type_label("future_resource") == "未知资源视角"
    assert period_preset_label("custom") == "自定义"
    assert period_preset_label("future_range") == "未知日期范围"
    assert gantt_view_label("operator") == "人员甘特"
    assert gantt_view_label("future_view") == "未知甘特视图"


def test_workbench_plan_role_labels_delegate_to_core_labels() -> None:
    for role, label in PLAN_ROLE_LABELS.items():
        assert plan_role_label(role) == label
    assert plan_role_label(None) == PLAN_ROLE_LABELS["adopted"]
    assert plan_role_label("future_role") == "未知方案身份"


# ===========================================================================
# 护栏与坏值拦放区（原 regression_scheduler_workbench_link_guardrails.py，10 函数）
# 🔴 B-2 红线：这是 R54「删手维 guard 面」依赖的逐键四态拦放 parity oracle。
# 以下 forbidden_keys 4-key 循环 / can_emit 12-case 矩阵 / is_comparison +
# is_superseded 全身份识别 / is_current_executable 翻转 + can_emit 后置 /
# preview·comparison execution_review 禁开 + scenario_id 不入 required_params，
# 均禁止任何去重 / 合并 / parametrize 折叠，整段逐字保留。
# 去重项：原 guardrails 的 _query_values helper 与本文件逐字一致，已去重为上方一份。
# ===========================================================================


def _assert_feedback_write_allowed(context: dict, expected: bool) -> None:
    assert can_emit_feedback_write_urls(context) is expected


def test_feedback_write_url_guardrail_is_explicit() -> None:
    current_official = {"plan_role": "adopted", "is_current_executable_official_version": True}
    cases = (
        (dict(current_official, can_dispatch=True, can_write_feedback=True), True),
        (dict(current_official, can_dispatch=True, can_write_feedback=False), False),
        (dict(current_official, can_dispatch=False, can_write_feedback=True), False),
        (dict(current_official, can_write_feedback=True, result_summary_parse_failed=True), False),
        ({"can_write_feedback": True}, False),
        ({"plan_role": "adopted", "can_write_feedback": True}, False),
        (dict(current_official, can_write_feedback=True), False),
        (dict(current_official, effective_plan_role="baseline_best", can_write_feedback=True), False),
        (
            {
                "requested_plan_role": "adopted",
                "effective_plan_role": "baseline_best",
                "is_current_executable_official_version": True,
                "can_write_feedback": True,
            },
            False,
        ),
        (dict(current_official, requested_plan_role="baseline_best", can_write_feedback=True), False),
        ({"plan_role": "baseline_best", "can_write_feedback": True}, False),
        ({"scenario_id": "preview-1", "can_write_feedback": True}, False),
    )
    for context, expected in cases:
        _assert_feedback_write_allowed(context, expected)

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
    base["is_current_executable_official_version"] = True
    missing_current_identity = dict(base)
    missing_current_identity.pop("is_current_executable_official_version", None)
    conflict_contexts = [
        dict(base, effective_plan_role="baseline_best"),
        dict(base, requested_plan_role="baseline_best"),
        dict(base, is_scenario_preview=True),
        dict(base, is_current_executable_official_version=False),
        dict(base, is_comparison=True),
        missing_current_identity,
    ]

    for context in conflict_contexts:
        link = build_workbench_link(context, "execution_review")
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]

    historical = build_workbench_link(dict(base, is_superseded_by_newer_version=True), "execution_review")
    assert historical["disabled"] is True
    assert historical["url"] == ""
    assert "历史正式方案" in historical["disabled_reason"]


def test_plan_guard_fields_keep_each_surface_shape() -> None:
    plan_resolution = {
        "requested_role": "adopted",
        "selected_role": "adopted",
        "status": "resolved_adopted",
        "is_scenario_preview": False,
        "is_comparison": False,
        "is_superseded_by_newer_version": True,
        "is_official": True,
        "is_preview": False,
        "is_current_executable_official_version": False,
        "can_dispatch": True,
        "can_write_feedback": True,
        "plan_identity_error": "identity-error",
        "plan_identity_blocking_error": True,
        "plan_identity_blocking_scope": "workbench_continuation",
        "result_summary_parse_failed": False,
        "result_summary_parse_reason": "",
    }

    report_context = build_workbench_plan_context(
        plan_role="adopted",
        plan_resolution=plan_resolution,
        plan_guard_fields=REPORT_PLAN_GUARD_FIELDS,
    )
    resource_context = build_workbench_plan_context(
        plan_role="adopted",
        plan_resolution=plan_resolution,
        plan_guard_fields=RESOURCE_PLAN_GUARD_FIELDS,
    )
    full_context = build_workbench_plan_context(
        plan_role="adopted",
        plan_resolution=plan_resolution,
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
    )

    assert report_context["is_superseded_by_newer_version"] is True
    assert "plan_role_status" not in report_context
    assert "plan_identity_error" not in report_context
    assert resource_context["plan_identity_error"] == "identity-error"
    assert "plan_role_status" not in resource_context
    assert full_context["plan_role_status"] == "resolved_adopted"
    assert full_context["plan_identity_blocking_scope"] == "workbench_continuation"


def test_full_plan_guard_fields_match_core_plan_role_filter_fields_for_resolution_shapes() -> None:
    base_identity = {
        "user_label": "正式采用方案",
        "can_dispatch": True,
        "can_write_feedback": True,
        "is_official": True,
        "is_preview": False,
        "is_current_executable_version": True,
        "is_current_executable_official_version": True,
        "is_superseded_by_newer_version": False,
        "result_summary_parse_failed": False,
        "result_summary_parse_reason": "",
        "schedule_result_status": "success",
    }
    plan_resolutions = [
        {
            "requested_role": "adopted",
            "selected_role": "adopted",
            "status": "resolved_adopted",
            "message": "",
            "source_table": SOURCE_SCHEDULE,
            "plan_identity": dict(base_identity),
        },
        {
            "requested_role": "baseline_best",
            "selected_role": "baseline_best",
            "status": "resolved_comparison",
            "message": "",
            "source_table": SOURCE_CANDIDATE_ROWS,
            "candidate_id": 101,
            "candidate_key": "baseline_best",
            "plan_identity": dict(base_identity, can_dispatch=False, can_write_feedback=False, is_official=False),
        },
        {
            "requested_role": "adopted",
            "selected_role": "adopted",
            "status": "resolved_comparison",
            "message": "正在预览模拟方案。",
            "source_table": SOURCE_SCHEDULE,
            "is_scenario_preview": True,
            "scenario_id": "SCN-1",
            "scenario_display_name": "模拟方案一",
            "plan_identity": dict(base_identity, can_dispatch=False, can_write_feedback=False, is_preview=True),
        },
        {
            "requested_plan_role": "baseline_best",
            "effective_plan_role": "adopted",
            "plan_role_status": "fallback_to_adopted",
            "plan_role_message": "已回退正式采用方案。",
            "source_table": SOURCE_SCHEDULE,
            "is_official_plan": True,
            "is_preview_plan": False,
            "is_current_executable_official_version": False,
            "can_dispatch": False,
            "can_write_feedback": False,
        },
        {
            "requested_role": "adopted",
            "selected_role": "adopted",
            "status": "resolved_adopted",
            "source_table": SOURCE_SCHEDULE,
            "can_dispatch": True,
            "can_write_feedback": True,
            "is_current_executable_official_version": True,
            "plan_identity": dict(base_identity, can_dispatch=False, can_write_feedback=False),
        },
    ]

    # N5：除"两投影实现互相一致"（下方 expected，从 core 侧派生）外，再钉一条独立 golden 基线——
    # 冻结当前正确的 guard 字段投影真值。原断言只证 plan_guard_fields_for_resolution 与
    # plan_role_filter_fields 同口径，若两者一起漂移（同源自反抓不到），本基线仍能抓行为回退。
    # 基线随 plan_resolutions 顺序一一对应；新增 shape 须同步补一条基线。
    expected_baseline = [
        {
            "requested_plan_role": "adopted", "effective_plan_role": "adopted",
            "plan_role_status": "resolved_adopted", "is_scenario_preview": False,
            "is_comparison": False, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": False,
            "is_current_executable_official_version": True, "can_dispatch": True,
            "can_write_feedback": True, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "baseline_best", "effective_plan_role": "baseline_best",
            "plan_role_status": "resolved_comparison", "is_scenario_preview": False,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": False, "is_preview_plan": False,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "adopted", "effective_plan_role": "adopted",
            "plan_role_status": "resolved_comparison", "is_scenario_preview": True,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": True,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "baseline_best", "effective_plan_role": "adopted",
            "plan_role_status": "fallback_to_adopted", "is_scenario_preview": False,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": False,
            "is_current_executable_official_version": False, "can_dispatch": False,
            "can_write_feedback": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "adopted", "effective_plan_role": "adopted",
            "plan_role_status": "resolved_adopted", "is_scenario_preview": False,
            "is_comparison": False, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": False,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
    ]
    assert len(expected_baseline) == len(plan_resolutions), "基线条数须与 plan_resolutions 一一对应"

    for index, plan_resolution in enumerate(plan_resolutions):
        core_fields = plan_role_filter_fields(plan_resolution)
        expected = {
            key: core_fields[key]
            for key in FULL_PLAN_GUARD_FIELDS
            if key in core_fields and core_fields[key] is not None
        }
        projected = plan_guard_fields_for_resolution(plan_resolution, FULL_PLAN_GUARD_FIELDS)
        assert projected == expected, f"shape[{index}]：guard 投影与 core 同口径 parity 失败"
        assert projected == expected_baseline[index], (
            f"shape[{index}]：guard 投影偏离冻结 golden 基线（行为回退，非仅同源不一致）"
        )


def test_execution_review_requires_current_executable_identity_before_read_only_review() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )
    context["can_dispatch"] = False

    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    context["is_current_executable_official_version"] = False
    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    context["is_current_executable_official_version"] = True
    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is False
    assert "plan_role=adopted" in link["url"]
    assert "scenario_id" not in _query_values(link["url"])
    assert context["can_write_feedback"] is False


def test_workbench_links_explain_blocking_identity_and_summary_parse_failure() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=True,
    )
    context["is_current_executable_official_version"] = True

    bad_identity = dict(
        context,
        plan_identity_blocking_error=True,
        plan_identity_error="请求里的方案身份不可用，已回到正式采用方案显示首页值班台。",
    )
    dispatch = build_workbench_link(bad_identity, "resource_dispatch")
    assert dispatch["disabled"] is True
    assert dispatch["url"] == ""
    assert "方案身份不可用" in dispatch["disabled_reason"]

    bad_summary = dict(
        context,
        can_dispatch=True,
        result_summary_parse_failed=True,
        result_summary_parse_reason="json_decode_error",
    )
    review = build_workbench_link(bad_summary, "execution_review")
    assert review["disabled"] is True
    assert review["url"] == ""
    assert "当前排产摘要读取失败" in review["disabled_reason"]
    assert "排产摘要内容不是有效 JSON" in review["disabled_reason"]
    assert "json_decode_error" not in review["disabled_reason"]

    unknown_summary = dict(
        context,
        can_dispatch=True,
        result_summary_parse_failed=True,
        result_summary_parse_reason="debug_stack_code",
    )
    unknown_review = build_workbench_link(unknown_summary, "execution_review")
    assert "当前排产摘要结构无法安全解析" in unknown_review["disabled_reason"]
    assert "debug_stack_code" not in unknown_review["disabled_reason"]


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
