"""回归测试：build_candidate_comparison_display 渲染候选方案对比的展示契约——按 plan_role 源表标记基线/关键链候选的「是否等同采用版/仅对比参考」、统计并罗列失败候选、把内部失败原因与时间预算用语翻成用户可懂中文、隐藏 graph_w*/关键链最好 等旧内部标签、且不重复采用方案后缀。"""

from __future__ import annotations

import json

from core.services.scheduler.schedule_plan_query_service import ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST
from data.repositories.schedule_plan_query_repo import SOURCE_SCHEDULE
from tests.candidate.test_scheduler_candidate_analysis_contract import (
    _comparison_summary,
    _plan_role_options,
    _plan_role_options_for_baseline_adopted,
    _plan_role_options_with_baseline_source,
)


def test_candidate_display_marks_baseline_best_as_adopted_when_baseline_is_selected() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(adopted_key="baseline"),
        selected_ver=7,
        plan_role_options=_plan_role_options_for_baseline_adopted(),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_BASELINE_BEST]["is_same_as_adopted"] is True
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "只作对比参考查看" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert rows[ROLE_CRITICAL_BEST]["is_same_as_adopted"] is False
    assert rows[ROLE_CRITICAL_BEST]["is_comparison"] is True
    assert "不能直接派工或反馈" in rows[ROLE_CRITICAL_BEST]["comparison_note"]


def test_candidate_display_uses_plan_role_source_table_for_comparison_state() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options_with_baseline_source(SOURCE_SCHEDULE),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert "candidate_key" not in rows[ROLE_BASELINE_BEST]
    assert "candidate_key" not in rows[ROLE_ADOPTED]
    assert "source_table" not in rows[ROLE_BASELINE_BEST]
    assert rows[ROLE_BASELINE_BEST]["is_same_as_adopted"] is False
    assert rows[ROLE_BASELINE_BEST]["is_comparison"] is True
    assert "对比参考方案" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "不能直接派工或反馈" in rows[ROLE_BASELINE_BEST]["comparison_note"]
    assert "正式排程已写入这一版" not in rows[ROLE_BASELINE_BEST]["comparison_note"]
    text = json.dumps(display, ensure_ascii=False, sort_keys=True)
    for forbidden in ("candidate_key", "source_table", "candidate_rows"):
        assert forbidden not in text


def test_candidate_display_surfaces_non_representative_failed_candidates() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    display = build_candidate_comparison_display(
        _comparison_summary(failed_extra=True),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    assert display["failed_candidate_count"] == 1
    assert any("重点工序优先方案 5/5" in label for label in display["failed_candidate_labels"])
    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "试算方案没算成功" in status_text
    assert "重点工序优先方案 5/5" in status_text
    rows = {row["role"]: row for row in display["rows"]}
    assert set(rows) == {ROLE_ADOPTED, ROLE_BASELINE_BEST, ROLE_CRITICAL_BEST}


def test_candidate_display_status_messages_include_candidate_run_state() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    comparison = summary["algo"]["candidate_comparison"]
    comparison["baseline_missing_or_failed"] = True
    comparison["skipped_candidate_labels"] = ["重点工序优先方案 4/5"]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "试算方案没算成功" in status_text
    assert "图分析失败：存在环" in status_text
    assert "原算法那套方案缺失或没算成功，请复核这次采用的结果。" in status_text
    assert "因为时间到了，系统没再开始这些方案：重点工序优先方案 4/5" in status_text
    assert "候选运行失败" not in status_text
    assert "时间上限" not in status_text
    assert "原算法候选" not in status_text
    assert "关键链候选" not in status_text


def test_candidate_display_translates_internal_failure_reason_for_users() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    failed_candidate = summary["algo"]["candidate_comparison"]["candidates"][-1]
    failed_candidate["label"] = "graph_w5_of_5"
    failed_candidate["failure_reason"] = "candidate_time_budget_reached"
    summary["algo"]["candidate_comparison"]["skipped_candidate_labels"] = ["graph_w4_of_5"]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "试算时间到了，系统没有继续算这套方案" in status_text
    assert "重点工序优先方案 5/5" in status_text
    assert "重点工序优先方案 4/5" in status_text
    assert "candidate_time_budget_reached" not in status_text
    assert "graph_w5_of_5" not in status_text
    assert "graph_w4_of_5" not in status_text


def test_candidate_display_translates_generic_failed_reason_for_users() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary(failed_extra=True)
    failed_candidate = summary["algo"]["candidate_comparison"]["candidates"][-1]
    failed_candidate["failure_reason"] = "candidate_failed"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    status_text = " ".join(message["text"] for message in display["status_messages"])
    assert "这套方案没有算成功" in status_text
    assert "candidate_failed" not in status_text


def test_candidate_display_and_plan_role_options_hide_old_internal_labels() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    visible_text = json.dumps(
        [(row["role_label"], row["candidate_label"]) for row in display["rows"]],
        ensure_ascii=False,
    )
    assert "关键链最好" not in visible_text
    assert "关键链候选" not in visible_text
    assert "graph_w" not in visible_text
    assert "重点工序优先方案" in visible_text

    option_text = json.dumps([option.to_dict() for option in _plan_role_options()], ensure_ascii=False)
    assert "关键链最好" not in option_text
    assert "关键链候选" not in option_text
    assert "重点工序优先方案" in option_text


def test_candidate_display_does_not_duplicate_adopted_plan_suffix() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    candidates = summary["algo"]["candidate_comparison"]["candidates"]
    candidates[0]["label"] = "最终采用方案"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    candidate_labels = [row["candidate_label"] for row in display["rows"]]
    assert "正式采用方案" in candidate_labels
    assert "正式采用方案方案" not in candidate_labels


def test_candidate_display_technical_score_label_does_not_leak_internal_score_items() -> None:
    from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

    summary = _comparison_summary()
    candidate = summary["algo"]["candidate_comparison"]["candidates"][1]
    candidate["score"] = [0, "op:SECRET-CANDIDATE", "OP010", {"node_id": "op:SECRET-NODE"}]

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    rows = {row["role"]: row for row in display["rows"]}
    assert rows[ROLE_ADOPTED]["technical_score_label"] == "0"
    rendered = json.dumps(display, ensure_ascii=False, sort_keys=True)
    for forbidden in ("op:", "OP010", "SECRET", "node_id"):
        assert forbidden not in rendered
