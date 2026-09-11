"""回归测试：排产分析页 analysis_action_hub 行动入口的契约——路由产出推荐卡与设备甘特图/人员甘特图/资源排班/超期清单链接并带 version/plan_role/批次/日期上下文，缺日期范围时链接禁用并提示，可见文案不泄露 plan_role/op_id 等内部术语，且详情区不重复 action_hub 的推荐。"""

from __future__ import annotations

from typing import Any, Dict

from tests._support.analysis_route_contract import (
    _build_app,
    _call_analysis_page,
    _comparison_summary,
    _HistoryServiceStub,
    _plan_role_options,
    _PlanRoleServiceMustNotBeCalled,
    _PlanRoleServiceStub,
)
from tests._support.paths import REPO_ROOT as PROJECT_ROOT

ACTION_HUB_TEMPLATE = "scheduler/analysis_parts/_action_hub.html"
CANDIDATE_TEMPLATE = "scheduler/analysis_parts/_candidate_comparison.html"
VISIBLE_FORBIDDEN_TERMS = (
    "plan_role",
    "scenario_id",
    "source_table",
    "candidate_id",
    "candidate_key",
    "op_id",
    "schedule_id",
    "baseline_best",
    "critical_best",
    "adopted",
    "selection_reason_code",
)


def _public_words(value):
    public_keys = {"title", "label", "candidate_label", "role_label", "comparison_note", "empty_state",
                   "notice", "text", "message", "disabled_reason", "summary", "reason", "note"}
    words = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key in public_keys and isinstance(item, str):
                words.append(item)
            elif isinstance(item, (dict, list)):
                words.append(_public_words(item))
    elif isinstance(value, list):
        words.extend(_public_words(item) for item in value)
    return "\n".join(words)


def _assert_old_parts_retired():
    for name in (ACTION_HUB_TEMPLATE, CANDIDATE_TEMPLATE, "scheduler/analysis.html"):
        assert not (PROJECT_ROOT / "templates" / name).exists()


def _payload(monkeypatch, path: str, summary: Dict[str, Any], plan_role_service: Any) -> Dict[str, Any]:
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app(monkeypatch)
    return _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path=path,
    )


def test_analysis_route_exposes_action_hub_with_context_links(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    hub = payload["analysis_action_hub"]
    assert hub["has_recommendation"] is True
    assert hub["recommendation_card"]["candidate_label"] == "重点工序优先方案 1/5"
    assert [card["role_label"] for card in hub["summary_cards"]] == [
        "正式采用方案",
        "原算法代表方案",
        "重点工序优先代表方案",
    ]
    assert [link["label"] for link in hub["next_links"]] == ["设备甘特图", "人员甘特图", "资源排班", "超期清单"]
    assert all("version=7" in link["url"] for link in hub["next_links"])
    assert all("plan_role=adopted" in link["url"] for link in hub["next_links"])
    assert all("required_params" in link for link in hub["next_links"])
    assert "周计划" not in [link["label"] for link in hub["next_links"]]


def test_analysis_action_hub_next_links_keep_resource_batch_and_date_context(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        (
            "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31"
            "&query_date=2026-05-28&period_preset=week"
            "&resource_type=machine&resource_id=M1&batch_id=B-001"
        ),
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    links = {link["label"]: link for link in payload["analysis_action_hub"]["next_links"]}

    for label in ("设备甘特图", "人员甘特图"):
        assert "start_date=2026-05-25" in links[label]["url"]
        assert "end_date=2026-05-31" in links[label]["url"]
        assert "gantt_batch=B-001" in links[label]["url"]
    assert "gantt_resource=M1" in links["设备甘特图"]["url"]
    assert "gantt_resource" not in links["人员甘特图"]["url"]

    dispatch_url = links["资源排班"]["url"]
    assert "date_from=2026-05-25" in dispatch_url
    assert "date_to=2026-05-31" in dispatch_url
    assert "query_date=2026-05-28" in dispatch_url
    assert "period_preset=custom" in dispatch_url
    assert "scope_type=machine" in dispatch_url
    assert "scope_id=M1" in dispatch_url
    assert "machine_id=M1" in dispatch_url
    assert "batch_id=B-001" in dispatch_url
    assert "batch_id=B-001" in links["超期清单"]["url"]


def test_analysis_action_hub_shows_disabled_reason_when_date_range_is_missing(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    hub = payload["analysis_action_hub"]
    _assert_old_parts_retired()
    visible = _public_words(hub)

    assert hub["next_links"]
    links = {link["label"]: link for link in hub["next_links"]}
    assert links["超期清单"]["disabled"] is False
    assert links["超期清单"]["url"]
    for label in ("设备甘特图", "人员甘特图", "资源排班"):
        assert links[label]["disabled"] is True
        assert links[label]["url"] == ""
    assert "日期范围" in visible
    assert "设备甘特图" in visible
    assert "资源排班" in visible


def test_analysis_action_hub_renders_visible_business_text_without_internal_terms(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    _assert_old_parts_retired()
    visible = _public_words(payload["analysis_action_hub"])

    assert "排产分析行动入口" in visible
    assert "系统建议采用" in visible
    assert "设备甘特图" in visible
    assert "资源排班" in visible
    assert "超期清单" in visible
    assert "排产诊断状态" in visible
    for forbidden in VISIBLE_FORBIDDEN_TERMS:
        assert forbidden not in visible


def test_analysis_action_hub_shows_plain_empty_state_without_candidate_comparison(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7",
        {"algo": {"metrics": {"overdue_count": 0}}},
        _PlanRoleServiceMustNotBeCalled(),
    )

    hub = payload["analysis_action_hub"]
    _assert_old_parts_retired()
    visible = _public_words(hub)

    assert hub["has_recommendation"] is False
    assert hub["summary_cards"] == []
    assert hub["next_links"] == []
    assert "本次没有开启方案对比" in visible
    assert "系统建议采用" not in visible
    for forbidden in VISIBLE_FORBIDDEN_TERMS:
        assert forbidden not in visible


def test_detailed_candidate_part_does_not_repeat_action_hub_recommendation(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    _assert_old_parts_retired()
    display = payload["candidate_comparison_display"]
    visible = _public_words(display["rows"])
    assert display["has_comparison"] is True and len(display["rows"]) == 3
    assert payload["analysis_action_hub"]["recommendation_card"] == display["recommendation_card"]
    assert "系统建议采用" not in visible
    assert visible.count("正式采用方案") >= 1


def test_detailed_candidate_part_keeps_legacy_recommendation_without_action_hub_context(monkeypatch) -> None:
    payload = _payload(monkeypatch,
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    _assert_old_parts_retired()
    display = payload["candidate_comparison_display"]
    visible = _public_words(display)
    assert display["has_comparison"] is True and len(display["rows"]) == 3
    assert "系统建议采用" in visible
    assert "正式采用方案" in visible
    assert display["recommendation_card"]["candidate_label"] == "重点工序优先方案 1/5"
