from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List

from web.viewmodels.dashboard_workbench import build_dashboard_workbench_summary

INTERNAL_VISIBLE_TOKENS = (
    "plan_role",
    "scenario_id",
    "source_table",
    "candidate_id",
    "op_id",
    "schedule_id",
)


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: List[str] = []

    def handle_data(self, data: str) -> None:
        text = str(data or "").strip()
        if text:
            self.parts.append(text)


def _visible_text_from_summary(summary: Dict[str, Any]) -> str:
    parts: List[str] = []
    for card in summary.get("risk_cards") or []:
        parts.extend(
            str(card.get(key) or "")
            for key in ("label", "value", "helper_text")
        )
    for todo in summary.get("todo_items") or []:
        parts.extend(
            str(todo.get(key) or "")
            for key in ("title", "impact_text", "evidence_text", "handling_state_label", "action_label")
        )
        for action_key in ("primary_action", "secondary_action"):
            action = todo.get(action_key) or {}
            parts.extend(str(action.get(key) or "") for key in ("label", "context_summary", "disabled_reason"))
    for link in summary.get("quick_links") or []:
        parts.extend(str(link.get(key) or "") for key in ("label", "context_summary", "disabled_reason"))
    parts.append(str(summary.get("realtime_note") or ""))
    parts.append(str(summary.get("empty_state") or ""))
    return "\n".join(parts)


def _todo_by_kind(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("kind")): item for item in summary.get("todo_items") or []}


def _action_targets(todo: Dict[str, Any]) -> List[str]:
    return [
        str((todo.get("primary_action") or {}).get("target_page") or ""),
        str((todo.get("secondary_action") or {}).get("target_page") or ""),
    ]


def _build_summary(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "pending_count": 2,
        "scheduled_count": 4,
        "overdue_count": 3,
        "latest_history": SimpleNamespace(version=12),
        "latest_summary": {
            "overdue_batches": {"count": 3},
            "algo": {
                "metrics": {"machine_util_avg": 0.91},
                "candidate_comparison": {
                    "planned_candidate_count": 3,
                    "completed_candidate_count": 2,
                    "adopted_candidate_key": "graph_w1_of_3",
                    "baseline_missing_or_failed": True,
                    "candidates": [{"candidate_key": "graph_w1_of_3"}],
                },
            },
        },
        "latest_summary_parse_state": {"parse_failed": False},
        "plan_time_span": {"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-07 18:00:00"},
        "today_rows": [
            {"op_id": 101, "start_time": "2026-06-01 08:00:00", "batch_id": "B1"},
            {"op_id": 102, "start_time": "2026-06-01 15:00:00", "batch_id": "B2"},
            {"op_id": 103, "start_time": "2026-06-01 09:00:00", "batch_id": "B3"},
        ],
        "execution_facts_by_op_id": {
            103: SimpleNamespace(actual_status="processing", actual_start_time=datetime(2026, 6, 1, 9, 5), actual_end_time=None)
        },
        "now": datetime(2026, 6, 1, 10, 0),
    }
    data.update(overrides)
    return build_dashboard_workbench_summary(**data)


def test_dashboard_workbench_summary_covers_required_todo_types_and_links() -> None:
    summary = _build_summary()
    todos = _todo_by_kind(summary)

    assert set(todos) == {"overdue", "resource_overload", "site_record_gap", "candidate_review"}
    assert len(summary["todo_items"]) <= 6
    assert "3 个批次会晚于交期" in todos["overdue"]["impact_text"]
    assert "91.0%" in todos["resource_overload"]["impact_text"]
    assert "1 道今天已到开始时间" in todos["site_record_gap"]["impact_text"]
    assert "未来任务没有计入" in todos["site_record_gap"]["evidence_text"]
    assert "方案需要确认" == todos["candidate_review"]["title"]
    assert "待处理项根据当前数据实时生成，暂不保存已处理状态。" == summary["realtime_note"]

    assert _action_targets(todos["overdue"]) == ["overdue_report", "delay_diagnosis"]
    assert _action_targets(todos["resource_overload"]) == ["resource_dispatch", "utilization_report"]
    assert _action_targets(todos["site_record_gap"]) == ["execution_review", "resource_dispatch"]
    assert _action_targets(todos["candidate_review"]) == ["analysis", "gantt"]

    for todo in summary["todo_items"]:
        for action_key in ("primary_action", "secondary_action"):
            action = todo[action_key]
            assert "label" in action
            assert "target_page" in action
            assert "required_params" in action

    visible_text = _visible_text_from_summary(summary)
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in visible_text
    assert "必须补录" not in visible_text


def test_dashboard_workbench_data_gap_and_resource_load_empty_state_are_plain_chinese() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_history=None,
        latest_summary=None,
        latest_summary_parse_state={"parse_failed": False},
        plan_time_span=None,
        today_rows=[],
        execution_facts_by_op_id={},
    )
    todos = _todo_by_kind(summary)
    cards = {str(item.get("kind")): item for item in summary.get("risk_cards") or []}

    assert set(todos) == {"data_gap"}
    assert "还没有排产版本" in todos["data_gap"]["impact_text"]
    assert cards["resource_overload"]["value"] == "数据不足"
    assert cards["resource_overload"]["value"] != "0%"
    assert "当前没有必须马上处理的排产风险" in summary["empty_state"]


def test_dashboard_workbench_parse_failure_becomes_data_gap_without_crashing() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_summary=None,
        latest_summary_parse_state={
            "parse_failed": True,
            "user_message": "当前版本的排产摘要读取失败，页面仅展示基础历史信息。",
        },
        plan_time_span={"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-07 18:00:00"},
        today_rows=[],
        execution_facts_by_op_id={},
    )
    todos = _todo_by_kind(summary)

    assert set(todos) == {"data_gap"}
    assert todos["data_gap"]["title"] == "最新排产摘要读取失败"
    assert "页面仅展示基础历史信息" in todos["data_gap"]["evidence_text"]


def test_visible_text_parser_helper_ignores_href_query_internal_fields() -> None:
    parser = _VisibleTextParser()
    parser.feed('<a href="/x?plan_role=adopted&op_id=1"><span>查看排产分析</span></a>')
    assert "plan_role" not in "\n".join(parser.parts)
    assert "op_id" not in "\n".join(parser.parts)
