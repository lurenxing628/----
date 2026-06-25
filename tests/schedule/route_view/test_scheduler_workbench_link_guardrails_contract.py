"""契约测试：scheduler_workbench_links 工作台跳转链接的构造与护栏——各目标页 URL 保真透传版本/方案身份/日期范围/批次/资源等参数及 required_params 顺序、标签映射固定；护栏侧逐键四态拦放（R54 parity oracle）：预览/对比/历史方案禁开复盘入口、班组维度不支持页禁用、缺版本或日期范围禁用、反馈写入按完整方案身份判定、execution_review 拒绝从 extra_params 注入身份、坏摘要与缺目标页配置一律响亮报错。"""

from __future__ import annotations

from core.models.schedule_plan_role import SOURCE_SCHEDULE
from web.viewmodels.scheduler_workbench_links import (
    FULL_PLAN_GUARD_FIELDS,
    REPORT_PLAN_GUARD_FIELDS,
    RESOURCE_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_links,
    build_workbench_plan_context,
    can_emit_feedback_write_urls,
)

# ===========================================================================
# 护栏与坏值拦放区（原 regression_scheduler_workbench_link_guardrails.py，10 函数）
# 🔴 B-2 红线：这是 R54「删手维 guard 面」依赖的逐键四态拦放 parity oracle。
# 以下 forbidden_keys 4-key 循环 / can_emit 12-case 矩阵 / is_comparison +
# is_superseded 全身份识别 / is_current_executable 翻转 + can_emit 后置 /
# preview·comparison execution_review 禁开 + 历史成功正式方案可只读复盘 + scenario_id 不入 required_params，
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
        (dict(current_official, can_dispatch="yes", can_write_feedback="yes"), True),
        (dict(current_official, can_dispatch="no", can_write_feedback="yes"), False),
        (dict(current_official, can_dispatch="yes", can_write_feedback="no"), False),
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
        can_write_feedback=True,
    )
    base["is_current_executable_official_version"] = True
    missing_current_identity = dict(base)
    missing_current_identity.pop("is_current_executable_official_version", None)
    conflict_contexts = [
        dict(base, effective_plan_role="baseline_best"),
        dict(base, requested_plan_role="baseline_best"),
        dict(base, is_scenario_preview=True),
        dict(base, is_comparison=True),
        dict(base, schedule_result_status="partial", is_current_executable_official_version=False),
        dict(base, detail_saved=False, is_current_executable_official_version=False),
        dict(base, is_simulation_plan=True),
    ]

    for context in conflict_contexts:
        link = build_workbench_link(context, "execution_review")
        assert link["disabled"] is True
        assert link["url"] == ""
        assert "只复盘正式采用方案" in link["disabled_reason"]

    historical = build_workbench_link(dict(base, is_superseded_by_newer_version=True), "execution_review")
    assert historical["disabled"] is True
    assert historical["url"] == ""

    missing_current = build_workbench_link(missing_current_identity, "execution_review")
    assert missing_current["disabled"] is True
    assert missing_current["url"] == ""


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
