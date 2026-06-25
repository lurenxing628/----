"""契约测试：scheduler_workbench_links 工作台跳转链接的构造与护栏——各目标页 URL 保真透传版本/方案身份/日期范围/批次/资源等参数及 required_params 顺序、标签映射固定；护栏侧逐键四态拦放（R54 parity oracle）：预览/对比/历史方案禁开复盘入口、班组维度不支持页禁用、缺版本或日期范围禁用、反馈写入按完整方案身份判定、execution_review 拒绝从 extra_params 注入身份、坏摘要与缺目标页配置一律响亮报错。"""

from __future__ import annotations

from urllib.parse import parse_qs, urlparse

from core.models.schedule_plan_role import SOURCE_CANDIDATE_ROWS, SOURCE_SCHEDULE
from core.services.scheduler.schedule_result_view_context import plan_role_filter_fields
from web.viewmodels.scheduler_workbench_link_query import plan_guard_fields_for_resolution
from web.viewmodels.scheduler_workbench_links import (
    FULL_PLAN_GUARD_FIELDS,
    build_workbench_link,
    build_workbench_links,
    build_workbench_plan_context,
)


def _query_values(url: str) -> dict:
    return {key: values[-1] for key, values in parse_qs(urlparse(url).query).items()}



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
        "detail_saved": True,
        "is_simulation": False,
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
            "can_write_feedback": True, "source_table": "schedule",
            "schedule_result_status": "success", "detail_saved": True,
            "is_simulation_plan": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "baseline_best", "effective_plan_role": "baseline_best",
            "plan_role_status": "resolved_comparison", "is_scenario_preview": False,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": False, "is_preview_plan": False,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "source_table": "candidate_rows",
            "schedule_result_status": "success", "detail_saved": True,
            "is_simulation_plan": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "adopted", "effective_plan_role": "adopted",
            "plan_role_status": "resolved_comparison", "is_scenario_preview": True,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": True,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "source_table": "schedule",
            "schedule_result_status": "success", "detail_saved": True,
            "is_simulation_plan": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "baseline_best", "effective_plan_role": "adopted",
            "plan_role_status": "fallback_to_adopted", "is_scenario_preview": False,
            "is_comparison": True, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": False,
            "is_current_executable_official_version": False, "can_dispatch": False,
            "can_write_feedback": False, "source_table": "schedule",
            "schedule_result_status": "", "detail_saved": False,
            "is_simulation_plan": False, "result_summary_parse_failed": False,
            "result_summary_parse_reason": "",
        },
        {
            "requested_plan_role": "adopted", "effective_plan_role": "adopted",
            "plan_role_status": "resolved_adopted", "is_scenario_preview": False,
            "is_comparison": False, "is_superseded_by_newer_version": False,
            "is_official_plan": True, "is_preview_plan": False,
            "is_current_executable_official_version": True, "can_dispatch": False,
            "can_write_feedback": False, "source_table": "schedule",
            "schedule_result_status": "success", "detail_saved": True,
            "is_simulation_plan": False, "result_summary_parse_failed": False,
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


def test_workbench_plan_context_parses_plan_identity_string_flags_before_review_guard() -> None:
    context = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        plan_resolution={
            "requested_role": "adopted",
            "selected_role": "adopted",
            "source_table": SOURCE_SCHEDULE,
            "is_comparison": "no",
            "is_scenario_preview": "no",
            "plan_identity": {
                "is_official": "yes",
                "is_preview": "no",
                "is_simulation": "no",
                "result_summary_parse_failed": "no",
                "schedule_result_status": "success",
                "detail_saved": "yes",
                "is_current_executable_official_version": "yes",
                "can_dispatch": "no",
                "can_write_feedback": "no",
            },
        },
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )

    assert context["is_comparison"] is False
    assert context["is_scenario_preview"] is False
    assert context["is_preview_plan"] is False
    assert context["is_simulation_plan"] is False
    assert context["result_summary_parse_failed"] is False
    assert context["detail_saved"] is True
    assert context["can_dispatch"] is False
    assert context["can_write_feedback"] is False
    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is False
    assert "plan_role=adopted" in link["url"]

    blocked = build_workbench_plan_context(
        version=12,
        plan_role="adopted",
        plan_resolution={
            "requested_role": "adopted",
            "selected_role": "adopted",
            "source_table": SOURCE_SCHEDULE,
            "plan_identity": {
                "is_official": "yes",
                "is_preview": "no",
                "is_simulation": "no",
                "result_summary_parse_failed": "yes",
                "schedule_result_status": "success",
                "detail_saved": "yes",
            },
        },
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
        date_from="2026-05-25",
        date_to="2026-05-31",
    )
    blocked_link = build_workbench_link(blocked, "execution_review")
    assert blocked["result_summary_parse_failed"] is True
    assert blocked_link["disabled"] is True
    assert blocked_link["url"] == ""


def test_execution_review_requires_reviewable_official_identity_before_read_only_review() -> None:
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
                "can_dispatch": False,
                "can_write_feedback": False,
            },
        },
        plan_guard_fields=FULL_PLAN_GUARD_FIELDS,
        date_from="2026-05-25",
        date_to="2026-05-31",
        can_write_feedback=False,
    )
    context["can_dispatch"] = False

    missing_status = dict(context, schedule_result_status="", is_current_executable_official_version=False)
    link = build_workbench_link(missing_status, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    missing_detail = dict(context, detail_saved=False, is_current_executable_official_version=False)
    link = build_workbench_link(missing_detail, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    detail_saved_no = dict(context, detail_saved="no", is_current_executable_official_version=False)
    link = build_workbench_link(detail_saved_no, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    parse_failed_no = dict(context, result_summary_parse_failed="no")
    link = build_workbench_link(parse_failed_no, "execution_review")
    assert link["disabled"] is False
    assert "plan_role=adopted" in link["url"]

    parse_failed_yes = dict(context, result_summary_parse_failed="yes")
    link = build_workbench_link(parse_failed_yes, "execution_review")
    assert link["disabled"] is True
    assert link["url"] == ""

    link = build_workbench_link(context, "execution_review")
    assert link["disabled"] is False
    assert "plan_role=adopted" in link["url"]
    assert "scenario_id" not in _query_values(link["url"])
    assert context["can_write_feedback"] is False

    historical = dict(context, is_current_executable_official_version=False, is_superseded_by_newer_version=True)
    historical_link = build_workbench_link(historical, "execution_review")
    assert historical_link["disabled"] is True
    assert historical_link["url"] == ""


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
