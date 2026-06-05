"""回归测试：方案对比展示(build_candidate_comparison_display)与诊断/降级视图只渲染大白话、绝不泄露内部术语(score/selection_reason_code/candidate_key/source_table/plan_role 等)——对比缺失/原因码未知/采用方案未完成时不伪造推荐卡，坏数值与未知状态走「记录异常」文案，对应模板只读公开字段。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, List

from regression_scheduler_candidate_analysis_contract import (
    _comparison_summary,
    _plan_role_options,
    _plan_role_options_for_baseline_adopted,
)

from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display
from web.viewmodels.scheduler_analysis_diagnostics import build_diagnostic_sections
from web.viewmodels.scheduler_degradation_presenter import build_primary_degradation
from web.viewmodels.scheduler_history_summary import format_public_datetime

REPO_ROOT = Path(__file__).resolve().parents[1]

INTERNAL_VISIBLE_TERMS = (
    "score",
    "selected_score",
    "score tuple",
    "selection_reason_code",
    "reason_code",
    "balanced_critical_health_better",
    "balanced_raw_score_best",
    "score_only_raw_score_best",
    "candidate_key",
    "graph_w1_of_5",
    "graph_w",
    "plan_role",
    "baseline_best",
    "critical_best",
    "adopted",
    "source_table",
    "candidate_rows",
    "schedule_candidate_selection",
    "candidate_id",
    "scenario_id",
    "[0, 0, 9.0]",
    "(0, 0, 9.0)",
)


def _visible_card_text(card: Any) -> str:
    assert isinstance(card, dict)
    values = [
        card.get("eyebrow"),
        card.get("title"),
        card.get("candidate_label"),
        card.get("reason"),
        card.get("note"),
    ]
    return " ".join(str(value or "") for value in values)


def _visible_summary_card_values(cards: Iterable[Any]) -> List[str]:
    values: List[str] = []
    for card in cards:
        assert isinstance(card, dict)
        values.append(str(card.get("role_label") or ""))
        values.append(str(card.get("candidate_label") or ""))
        values.append(str(card.get("comparison_note") or ""))
        for metric in list(card.get("metrics") or []):
            assert isinstance(metric, dict)
            values.append(str(metric.get("label") or ""))
            values.append(str(metric.get("value") or ""))
            values.append(str(metric.get("comparison_text") or ""))
    return values


def _assert_plain_card(card: Any, *, expected_candidate: str) -> None:
    text = _visible_card_text(card)
    assert "推荐结论" in text
    assert "系统建议采用" in text
    assert expected_candidate in text
    assert "正式采用方案" in text
    assert "不能直接派工或提交现场反馈" in text
    for forbidden in INTERNAL_VISIBLE_TERMS:
        assert forbidden not in text


def _assert_payload_not_leaking_internal_text(values: Iterable[Any]) -> None:
    text = json.dumps(list(values), ensure_ascii=False)
    for forbidden in INTERNAL_VISIBLE_TERMS:
        assert forbidden not in text


def test_candidate_recommendation_card_uses_plain_language_for_critical_plan() -> None:
    summary = _comparison_summary()
    summary["algo"]["candidate_comparison"]["selection_reason_code"] = "balanced_critical_health_better"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    _assert_plain_card(display["recommendation_card"], expected_candidate="重点工序优先方案 1/5")
    assert "系统综合查看交期和整体表现" in display["recommendation_card"]["reason"]


def test_candidate_recommendation_card_uses_plain_language_for_baseline_plan() -> None:
    display = build_candidate_comparison_display(
        _comparison_summary(adopted_key="baseline"),
        selected_ver=7,
        plan_role_options=_plan_role_options_for_baseline_adopted(),
    )

    _assert_plain_card(display["recommendation_card"], expected_candidate="原算法方案")


def test_candidate_recommendation_card_is_not_faked_when_comparison_is_missing() -> None:
    display = build_candidate_comparison_display(
        {"algo": {"metrics": {"overdue_count": 0}}},
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    assert display["has_comparison"] is False
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "本次没有开启方案对比" in display["notice"]


def test_candidate_recommendation_card_is_not_faked_when_reason_code_is_unknown() -> None:
    summary = _comparison_summary()
    raw_reason = "future_reason_code"
    summary["algo"]["candidate_comparison"]["selection_reason_code"] = raw_reason

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    assert display["selection_reason_parse_failed"] is True
    assert display["recommendation_card"] is None
    assert "推荐理由记录异常" in display["selection_reason_label"]
    assert raw_reason not in json.dumps(display, ensure_ascii=False)


def test_candidate_recommendation_card_is_not_faked_when_adopted_candidate_did_not_complete() -> None:
    for status, status_label in (("failed", "失败"), ("skipped", "已跳过")):
        summary = _comparison_summary()
        comparison = summary["algo"]["candidate_comparison"]
        adopted_key = comparison["adopted_candidate_key"]
        for candidate in comparison["candidates"]:
            if candidate["candidate_key"] == adopted_key:
                candidate["status"] = status

        display = build_candidate_comparison_display(
            summary,
            selected_ver=7,
            plan_role_options=_plan_role_options(),
        )

        assert display["recommendation_card"] is None
        assert display["selection_reason_label"] == ""
        status_text = " ".join(message["text"] for message in display["status_messages"])
        assert status_label in status_text
        assert "系统不展示推荐结论" in status_text


def test_candidate_comparison_incomplete_history_uses_plain_notice_without_fake_cards() -> None:
    display = build_candidate_comparison_display(
        _comparison_summary(incomplete=True),
        selected_ver=7,
        plan_role_options=[],
    )

    assert display["has_comparison"] is False
    assert display["rows"] == []
    assert display["recommendation_card"] is None
    assert display["summary_cards"] == []
    assert "本次方案对比记录不完整，当前只展示正式采用方案" in display["notice"]
    _assert_payload_not_leaking_internal_text([display["notice"]])


def test_candidate_link_empty_state_uses_plain_public_reason() -> None:
    source = (REPO_ROOT / "templates/scheduler/analysis_parts/_candidate_comparison.html").read_text(encoding="utf-8")

    assert "row.link_unavailable_reason" in source
    assert "暂无可跳转明细" in source
    link_block = source[source.index("{% if row.links and row.links|length > 0 %}") : source.index("</td>", source.index("{% if row.links and row.links|length > 0 %}"))]
    assert "row.detail_saved" not in link_block
    assert "row.source_table" not in link_block
    assert "candidate_id" not in link_block


def test_candidate_recommendation_template_only_reads_public_card_fields() -> None:
    source = (REPO_ROOT / "templates/scheduler/analysis_parts/_candidate_comparison.html").read_text(encoding="utf-8")
    start = source.index("{% if candidate_comparison_display.recommendation_card %}")
    end = source.index("{% elif candidate_comparison_display.selection_reason_label %}")
    block = source[start:end]

    assert "recommendation_card.eyebrow" in block
    assert "recommendation_card.title" in block
    assert "recommendation_card.candidate_label" in block
    assert "recommendation_card.reason" in block
    assert "recommendation_card.note" in block
    for forbidden in (
        "selection_reason_code",
        "candidate_key",
        "source_table",
        "candidate_id",
        "row.score",
        "score_label",
        "technical_score",
        "tuple",
        "参考分",
        "差值",
        "delta",
        "diff",
    ):
        assert forbidden not in block


def test_candidate_summary_cards_template_uses_public_fields_after_recommendation() -> None:
    source = (REPO_ROOT / "templates/scheduler/analysis_parts/_candidate_comparison.html").read_text(encoding="utf-8")
    recommendation_pos = source.index("{% if candidate_comparison_display.recommendation_card %}")
    summary_pos = source.index("{% if candidate_comparison_display.summary_cards %}")
    table_pos = source.index("analysisCandidateComparisonTable")
    block = source[summary_pos:table_pos]

    assert recommendation_pos < summary_pos < table_pos
    assert 'aria-label="代表方案摘要"' in block
    assert "aps-summary-grid" in block
    assert "aps-summary-item" in block
    assert "flash-card" not in block
    assert "candidate_comparison_display.summary_cards" in block
    assert "card.role_label" in block
    assert "card.candidate_label" in block
    assert "card.comparison_note" in block
    assert "card.metrics" in block
    assert "metric.label" in block
    assert "metric.value" in block
    assert "metric.comparison_text" in block
    for forbidden in (
        "row.score",
        "score_label",
        "technical_score",
        "candidate_key",
        "source_table",
        "candidate_id",
        "selection_reason_code",
        "compare_plan_role",
        "batch_impacts",
        "resource_impacts",
        "affected_batches",
        "参考分",
        "delta",
        "diff",
    ):
        assert forbidden not in block


def test_candidate_recommendation_visible_payload_hides_internal_fields() -> None:
    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    card = display["recommendation_card"]
    visible_values = [
        card["eyebrow"],
        card["title"],
        card["candidate_label"],
        card["reason"],
        card["note"],
        display["notice"],
    ]
    _assert_payload_not_leaking_internal_text(visible_values)


def test_candidate_summary_cards_visible_payload_hides_internal_fields() -> None:
    display = build_candidate_comparison_display(
        _comparison_summary(),
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    visible_values = _visible_summary_card_values(display["summary_cards"])
    assert "比正式采用方案多了" in " ".join(visible_values)
    assert "比正式采用方案少了" in " ".join(visible_values)
    assert "和正式采用方案基本持平" in " ".join(visible_values)
    _assert_payload_not_leaking_internal_text(visible_values)


def test_candidate_summary_cards_visible_payload_uses_plain_no_data_copy() -> None:
    summary = _comparison_summary()
    summary["algo"]["candidate_comparison"]["candidates"][0]["metrics"].pop("makespan_hours")

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    visible_text = " ".join(_visible_summary_card_values(display["summary_cards"]))
    assert "暂无数据" in visible_text
    assert "暂无对比数据" in visible_text
    assert "None" not in visible_text
    assert "nan" not in visible_text
    assert "null" not in visible_text


def test_candidate_label_internal_enum_does_not_become_public_label() -> None:
    summary = _comparison_summary()
    comparison = summary["algo"]["candidate_comparison"]
    adopted_key = comparison["adopted_candidate_key"]
    for candidate in comparison["candidates"]:
        if candidate["candidate_key"] == adopted_key:
            candidate["label"] = "critical_chain_best"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )

    visible_text = json.dumps(_visible_summary_card_values(display["summary_cards"]), ensure_ascii=False)
    assert "critical_chain_best" not in visible_text
    assert "重点工序优先方案" in visible_text


def test_candidate_bad_failed_count_uses_public_record_error_message() -> None:
    summary = _comparison_summary()
    summary["algo"]["candidate_comparison"]["failed_candidate_count"] = "bad-count"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )
    message_text = " ".join(item["text"] for item in display["status_messages"])

    assert "试算方案失败数量记录异常" in message_text
    assert "bad-count" not in message_text


def test_diagnostic_bad_number_and_unknown_graph_message_are_public_errors() -> None:
    sections = build_diagnostic_sections(
        {
            "algo": {
                "graph_analysis": {
                    "status": "available",
                    "node_count": "bad-count",
                    "message": "Traceback: raw internal_field failure",
                }
            }
        },
        selected_ver=7,
    )
    text = json.dumps(sections, ensure_ascii=False)

    assert "诊断数据异常" in text
    assert "诊断数据包含无法安全展示的数值，系统已停止本诊断块计算。" in text
    assert "无法当作 0 展示" not in text
    assert "raw internal_field" not in text


def test_diagnostic_unknown_graph_message_is_not_echoed() -> None:
    sections = build_diagnostic_sections(
        {
            "algo": {
                "graph_analysis": {
                    "status": "available",
                    "node_count": 1,
                    "edge_count": 0,
                    "critical_path_minutes": 0,
                    "cycle_edge_count": 0,
                    "time_cost_ms": 1,
                    "message": "Traceback: raw internal_field failure",
                }
            }
        },
        selected_ver=7,
    )
    text = json.dumps(sections, ensure_ascii=False)

    assert "图分析状态记录异常" in text
    assert "raw internal_field" not in text


def test_history_bad_datetime_uses_record_error_label() -> None:
    assert format_public_datetime("debug raw schedule_time") == "时间记录异常"
    assert format_public_datetime("2026-02-31 10:00") == "时间记录异常"


def test_candidate_missing_status_is_not_rendered_as_table_dash_or_bad_status() -> None:
    summary = _comparison_summary()
    summary["algo"]["candidate_comparison"]["candidates"][0]["status"] = ""

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )
    text = json.dumps(display["rows"], ensure_ascii=False)

    assert "状态没有确认" in text
    assert "状态记录异常" not in text


def test_candidate_unknown_status_does_not_keep_raw_bad_value() -> None:
    summary = _comparison_summary()
    summary["algo"]["candidate_comparison"]["candidates"][0]["status"] = "future_status"

    display = build_candidate_comparison_display(
        summary,
        selected_ver=7,
        plan_role_options=_plan_role_options(),
    )
    text = json.dumps(display["rows"], ensure_ascii=False)

    assert "状态记录异常" in text
    assert "future_status" not in text


def test_degradation_duplicate_later_bad_count_is_not_swallowed() -> None:
    display = build_primary_degradation(
        {
            "degradation_events": [
                {"code": "resource_pool_degraded", "message": "", "count": 1},
                {"code": "resource_pool_degraded", "message": "", "count": "bad-count"},
            ]
        }
    )

    assert display is not None
    assert "资源池资料不完整（数量记录异常）" in display["details"]


def test_degradation_duplicate_good_counts_are_accumulated() -> None:
    display = build_primary_degradation(
        {
            "degradation_events": [
                {"code": "resource_pool_degraded", "message": "", "count": 1},
                {"code": "resource_pool_degraded", "message": "", "count": 2},
            ]
        }
    )

    assert display is not None
    assert "资源池资料不完整（3）" in display["details"]
