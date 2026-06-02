from __future__ import annotations

from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader, select_autoescape
from regression_scheduler_candidate_analysis_contract import (
    _build_app,
    _call_analysis_page,
    _comparison_summary,
    _HistoryServiceStub,
    _plan_role_options,
    _PlanRoleServiceMustNotBeCalled,
    _PlanRoleServiceStub,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_TEMPLATE = PROJECT_ROOT / "templates/scheduler/analysis.html"
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


class _TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self.parts.append(text)

    @property
    def text(self) -> str:
        return " ".join(self.parts)


def _visible_text(html: str) -> str:
    parser = _TextCollector()
    parser.feed(html)
    return parser.text


def _render_part(part_name: str, **ctx: Any) -> str:
    env = Environment(
        loader=FileSystemLoader(str(PROJECT_ROOT / "templates")),
        autoescape=select_autoescape(("html", "xml")),
    )
    template = env.from_string("{% import 'components/ui_macros.html' as ui %}" f"{{% include '{part_name}' %}}")
    return template.render(**ctx)


def _payload(path: str, summary: Dict[str, Any], plan_role_service: Any) -> Dict[str, Any]:
    history_service = _HistoryServiceStub(summary)
    app, route_mod = _build_app()
    return _call_analysis_page(
        app,
        route_mod,
        history_service=history_service,
        plan_role_service=plan_role_service,
        path=path,
    )


def test_analysis_page_places_action_hub_before_detailed_sections() -> None:
    source = ANALYSIS_TEMPLATE.read_text(encoding="utf-8")

    selected_overview_pos = source.index("_selected_overview.html")
    action_hub_pos = source.index("_action_hub.html")
    warnings_pos = source.index("_summary_warnings.html")
    candidate_pos = source.index("_candidate_comparison.html")
    diagnostics_pos = source.index("_diagnostic_sections.html")
    metrics_pos = source.index("_metric_cards.html")
    process_pos = source.index("_optimization_process.html")

    assert selected_overview_pos < action_hub_pos < warnings_pos
    assert warnings_pos < candidate_pos < diagnostics_pos < metrics_pos < process_pos


def test_analysis_action_hub_places_diagnostics_before_next_actions() -> None:
    source = (PROJECT_ROOT / "templates/scheduler/analysis_parts/_action_hub.html").read_text(encoding="utf-8")

    assert source.index("analysis_action_hub.recommendation_card") < source.index("analysis_action_hub.summary_cards")
    assert source.index("analysis_action_hub.summary_cards") < source.index("analysis_action_hub.diagnostic_cards")
    assert source.index("analysis_action_hub.diagnostic_cards") < source.index("analysis_action_hub.next_links")


def test_analysis_route_exposes_action_hub_with_context_links() -> None:
    payload = _payload(
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


def test_analysis_action_hub_next_links_keep_resource_batch_and_date_context() -> None:
    payload = _payload(
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


def test_analysis_action_hub_shows_disabled_reason_when_date_range_is_missing() -> None:
    payload = _payload(
        "/scheduler/analysis?version=7",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    hub = payload["analysis_action_hub"]
    html = _render_part(ACTION_HUB_TEMPLATE, analysis_action_hub=hub)
    visible = _visible_text(html)

    assert hub["next_links"]
    assert all(link["disabled"] is True for link in hub["next_links"])
    assert all(link["url"] == "" for link in hub["next_links"])
    assert "日期范围" in visible
    assert "设备甘特图" in visible
    assert "资源排班" in visible


def test_analysis_action_hub_renders_visible_business_text_without_internal_terms() -> None:
    payload = _payload(
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    html = _render_part(ACTION_HUB_TEMPLATE, analysis_action_hub=payload["analysis_action_hub"])
    visible = _visible_text(html)

    assert "排产分析行动入口" in visible
    assert "系统建议采用" in visible
    assert "设备甘特图" in visible
    assert "资源排班" in visible
    assert "超期清单" in visible
    assert "排产诊断状态" in visible
    for forbidden in VISIBLE_FORBIDDEN_TERMS:
        assert forbidden not in visible


def test_analysis_action_hub_shows_plain_empty_state_without_candidate_comparison() -> None:
    payload = _payload(
        "/scheduler/analysis?version=7",
        {"algo": {"metrics": {"overdue_count": 0}}},
        _PlanRoleServiceMustNotBeCalled(),
    )

    hub = payload["analysis_action_hub"]
    html = _render_part(ACTION_HUB_TEMPLATE, analysis_action_hub=hub)
    visible = _visible_text(html)

    assert hub["has_recommendation"] is False
    assert hub["summary_cards"] == []
    assert hub["next_links"] == []
    assert "本次没有开启方案对比" in visible
    assert "系统建议采用" not in visible
    for forbidden in VISIBLE_FORBIDDEN_TERMS:
        assert forbidden not in visible


def test_detailed_candidate_part_does_not_repeat_action_hub_recommendation() -> None:
    payload = _payload(
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    html = _render_part(
        CANDIDATE_TEMPLATE,
        candidate_comparison_display=payload["candidate_comparison_display"],
        analysis_action_hub=payload["analysis_action_hub"],
    )
    visible = _visible_text(html)

    assert "方案对比" in visible
    assert "analysisCandidateComparisonTable" in html
    assert "系统建议采用" not in visible
    assert visible.count("正式采用方案") >= 1


def test_detailed_candidate_part_keeps_legacy_recommendation_without_action_hub_context() -> None:
    payload = _payload(
        "/scheduler/analysis?version=7&date_from=2026-05-25&date_to=2026-05-31",
        _comparison_summary(),
        _PlanRoleServiceStub(_plan_role_options()),
    )

    html = _render_part(CANDIDATE_TEMPLATE, candidate_comparison_display=payload["candidate_comparison_display"])
    visible = _visible_text(html)

    assert "方案对比" in visible
    assert "系统建议采用" in visible
    assert "正式采用方案" in visible
    assert "analysisCandidateComparisonTable" in html
