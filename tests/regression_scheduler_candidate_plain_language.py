from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from regression_scheduler_candidate_analysis_contract import (
    _comparison_summary,
    _plan_role_options,
    _plan_role_options_for_baseline_adopted,
)

from web.viewmodels.scheduler_analysis_candidates import build_candidate_comparison_display

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
    assert "本次没有开启方案对比" in display["notice"]


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
