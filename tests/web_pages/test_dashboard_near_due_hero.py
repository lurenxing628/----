"""回归：临期（near_due）在 hero 排序中的自然涌现 + 第 7 格临期卡跳转去向。

fusion-due-soon-alert 验收场景 2（hero 顶格）与场景 1（第 7 格可点跳甘特）的正向证据。
临期 severity=warning，按 _todo_items 既有排序键 (_SEVERITY_ORDER[severity], str(kind)) 自然决定 hero——
本 feature 不改排序逻辑，这里钉住「无超期+仅临期→临期顶 hero」「有超期→超期顶 hero、临期落 rest」
「无超期但有 data_gap(warning)→data_gap 顶 hero（kind 字母序 data_gap<near_due）、临期落 rest」三分支。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List
from urllib.parse import urlparse

from web.viewmodels.dashboard_workbench import build_dashboard_workbench_summary

# 干净底座：负荷低（不触发 resource_overload）、无今日计划（无 site_record_gap）、
# 摘要可用且版本/日期齐全（不触发 data_gap），故除超期/临期外无其它待办类别。
_CLEAN_BASE = dict(
    pending_count=0,
    latest_history=SimpleNamespace(version=12, created_at="2026-06-01 09:00:00", strategy="priority_first"),
    latest_summary={"algo": {"metrics": {"machine_util_avg": 0.5}}},
    latest_summary_parse_state={"parse_failed": False},
    plan_time_span={"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-07 18:00:00"},
    today_rows=[],
    execution_facts_by_op_id={},
    navigation_context={
        "version": "12", "plan_role": "adopted", "requested_plan_role": "adopted",
        "effective_plan_role": "adopted", "is_current_executable_official_version": True,
        "can_write_feedback": True,
    },
    now=datetime(2026, 6, 1, 10, 0),
)


def _todo_kinds(summary: Dict[str, Any]) -> List[str]:
    return [str(t.get("kind")) for t in summary.get("todo_items") or []]


def _card_by_kind(summary: Dict[str, Any], kind: str) -> Dict[str, Any]:
    return {str(c.get("kind")): c for c in summary.get("risk_cards") or []}[kind]


def test_near_due_tops_hero_when_no_overdue() -> None:
    # 场景 2 分支①：无超期、无其它同档更靠前 warning → 临期 todo 顶 hero（todo_items 第 1 条即 hero）
    summary = build_dashboard_workbench_summary(overdue_count=0, near_due_count=3, **_CLEAN_BASE)
    kinds = _todo_kinds(summary)
    assert kinds[:1] == ["near_due"], f"无超期时临期应顶 hero，实际 todo_items={kinds}"
    # 场景 1：第 7 格临期卡（count>0）可点跳设备甘特图
    card = _card_by_kind(summary, "near_due_batches")
    assert card["severity"] == "warning" and card["value"] == "3"
    assert urlparse(card["link"]["url"]).path == "/scheduler/gantt", f"临期卡应跳甘特，实际 {card['link']['url']}"


def test_overdue_tops_hero_near_due_falls_to_rest() -> None:
    # 场景 2 分支②：有超期(danger) → 超期顶 hero、临期(warning)落 rest_todos
    summary = build_dashboard_workbench_summary(overdue_count=2, near_due_count=3, **_CLEAN_BASE)
    kinds = _todo_kinds(summary)
    assert kinds[:1] == ["overdue"], f"有超期时超期应顶 hero，实际 {kinds}"
    rest_kinds = [str(t.get("kind")) for t in summary.get("rest_todos") or []]
    assert "near_due" in rest_kinds, f"有超期时临期应落 rest_todos，实际 rest={rest_kinds}"


def test_data_gap_tops_hero_over_near_due_by_kind_order() -> None:
    # 场景 2 分支③：无超期但有 data_gap(warning) → data_gap 顶 hero（kind 字母序 data_gap<near_due）、临期落 rest
    base = dict(_CLEAN_BASE)
    base["latest_history"] = None  # 触发 data_gap「基础数据还不够」(warning)
    summary = build_dashboard_workbench_summary(overdue_count=0, near_due_count=3, **base)
    kinds = _todo_kinds(summary)
    assert kinds[:1] == ["data_gap"], f"无超期但有 data_gap 时 data_gap 应顶 hero，实际 {kinds}"
    rest_kinds = [str(t.get("kind")) for t in summary.get("rest_todos") or []]
    assert "near_due" in rest_kinds, f"临期应落 rest，实际 rest={rest_kinds}"
