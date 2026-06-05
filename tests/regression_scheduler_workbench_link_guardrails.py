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
