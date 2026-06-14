"""回归测试：build_dashboard_workbench_summary 生成的首页工作台摘要必须覆盖 overdue/resource_overload/site_record_gap/candidate_review 等待办类型、保持链接携带 version 与 plan_role 等导航上下文、对各类读取失败（摘要解析失败、计划时间范围、现场事实、今日计划）退化为 data_gap 而非伪造 0，且对外可见文本绝不泄露 plan_role/op_id 等内部字段。"""

from __future__ import annotations

from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import Any, Dict, Iterable, List
from urllib.parse import parse_qs, urlparse

import pytest

from web.viewmodels.dashboard_workbench import (
    _machine_util_ratio,
    _parse_datetime,
    build_dashboard_workbench_summary,
)

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
    # fusion-dashboard-cockpit：页面渲染 hero（含失败合成物/超期精简线索等新文本）+ rest_todos
    # （⊂ todo_items，仍逐项扫描覆盖）+ 6 格 + 按钮墙 quick_links，故须扩扫 hero。
    parts = (
        _summary_hero_text(summary)
        + _summary_card_text(summary)
        + _summary_todo_text(summary)
        + _summary_quick_link_text(summary)
        + [str(summary.get("realtime_note") or ""), str(summary.get("empty_state") or "")]
    )
    return "\n".join(parts)


def _summary_hero_text(summary: Dict[str, Any]) -> List[str]:
    hero = summary.get("hero") or {}
    parts = _field_text(hero, ("title", "impact_text", "evidence_text"))
    for action_key in ("primary_action", "secondary_action"):
        parts.extend(_field_text(hero.get(action_key) or {}, ("label", "context_summary", "disabled_reason")))
    return parts


def _field_text(item: Dict[str, Any], fields: Iterable[str]) -> List[str]:
    return [str(item.get(key) or "") for key in fields]


def _summary_card_text(summary: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for card in summary.get("risk_cards") or []:
        parts.extend(_field_text(card, ("label", "value", "helper_text")))
    return parts


def _summary_todo_text(summary: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for todo in summary.get("todo_items") or []:
        parts.extend(_field_text(todo, ("title", "impact_text", "evidence_text", "handling_state_label", "action_label")))
        parts.extend(_todo_action_text(todo))
    return parts


def _todo_action_text(todo: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for action_key in ("primary_action", "secondary_action"):
        parts.extend(_field_text(todo.get(action_key) or {}, ("label", "context_summary", "disabled_reason")))
    return parts


def _summary_quick_link_text(summary: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for link in summary.get("quick_links") or []:
        parts.extend(_field_text(link, ("label", "context_summary", "disabled_reason")))
    return parts


def _todo_by_kind(summary: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {str(item.get("kind")): item for item in summary.get("todo_items") or []}


def _action_paths(todo: Dict[str, Any]) -> List[str]:
    return [
        urlparse(str((todo.get("primary_action") or {}).get("url") or "")).path,
        urlparse(str((todo.get("secondary_action") or {}).get("url") or "")).path,
    ]


def _query(url: str) -> Dict[str, List[str]]:
    return parse_qs(urlparse(url).query)


def _build_summary(**overrides: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {
        "pending_count": 2,
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
        "navigation_context": {
            "version": "12",
            "plan_role": "adopted",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "is_current_executable_official_version": True,
            "can_write_feedback": True,
        },
        "now": datetime(2026, 6, 1, 10, 0),
    }
    data.update(overrides)
    return build_dashboard_workbench_summary(**data)


def _assert_required_todo_content(summary: Dict[str, Any], todos: Dict[str, Dict[str, Any]]) -> None:
    assert set(todos) == {"overdue", "resource_overload", "site_record_gap", "candidate_review"}
    assert len(summary["todo_items"]) <= 6
    assert "3 个批次会晚于交期" in todos["overdue"]["impact_text"]
    assert "91.0%" in todos["resource_overload"]["impact_text"]
    assert "1 道今天已到开始时间" in todos["site_record_gap"]["impact_text"]
    assert "未来任务没有计入" in todos["site_record_gap"]["evidence_text"]
    assert "方案需要确认" == todos["candidate_review"]["title"]
    assert "待处理项根据当前数据实时生成，暂不保存已处理状态。" == summary["realtime_note"]


def _assert_required_todo_paths(todos: Dict[str, Dict[str, Any]]) -> None:
    assert _action_paths(todos["overdue"]) == ["/reports/overdue", "/reports/overdue"]
    assert _action_paths(todos["resource_overload"]) == ["/scheduler/resource-dispatch", "/reports/utilization"]
    assert _action_paths(todos["site_record_gap"]) == ["/reports/execution-review", "/scheduler/resource-dispatch"]
    assert _action_paths(todos["candidate_review"]) == ["/scheduler/analysis", "/scheduler/gantt"]


def _assert_todo_actions_have_labels(summary: Dict[str, Any]) -> None:
    for todo in summary["todo_items"]:
        for action_key in ("primary_action", "secondary_action"):
            assert str(todo[action_key].get("label") or "")


def _assert_visible_text_has_no_internal_tokens(summary: Dict[str, Any]) -> None:
    visible_text = _visible_text_from_summary(summary)
    for token in INTERNAL_VISIBLE_TOKENS:
        assert token not in visible_text
    assert "必须补录" not in visible_text


def test_dashboard_workbench_summary_covers_required_todo_types_and_links() -> None:
    summary = _build_summary()
    todos = _todo_by_kind(summary)

    _assert_required_todo_content(summary, todos)
    _assert_required_todo_paths(todos)
    _assert_todo_actions_have_labels(summary)
    _assert_visible_text_has_no_internal_tokens(summary)
    assert summary["summary_stats"]["overdue_count_value"] == "3"


def test_dashboard_six_cell_health_table_composition() -> None:
    summary = _build_summary()
    cards = {str(card.get("kind")): card for card in summary["risk_cards"]}

    # 恰 6 格且顺序锁定（验收 c4）：超期/待排/方案待确认/现场情况/资源负荷/基础数据
    assert [str(c.get("kind")) for c in summary["risk_cards"]] == [
        "overdue_batches",
        "pending_batches",
        "candidate_review",
        "site_record_gap",
        "resource_overload",
        "data_gap",
    ]
    # 删的两格不复活（版本归胶囊、已排不上首页）
    assert "latest_version" not in cards
    assert "scheduled_batches" not in cards
    # 待排格点跳 → 执行排产 'batches'（/scheduler/，context-free），路径正确且 query 为空（不泄漏上下文）
    pending_url = cards["pending_batches"]["link"]["url"]
    assert urlparse(pending_url).path == "/scheduler/"
    assert _query(pending_url) == {}
    # 健康场景：方案待确认有候选→notice/计数；基础数据无缺口→ok 灰
    assert cards["candidate_review"]["severity"] == "notice"
    assert cards["candidate_review"]["value"] == "3"
    assert cards["data_gap"]["severity"] == "ok"


def test_dashboard_candidate_cell_respects_disabled_flag() -> None:
    # candidate_comparison.enabled=False（候选生成关闭）→ 与分析页同口径视为无候选，
    # 不误报「方案待确认」：卡显「无」/ok 灰、候选 todo 缺席
    summary = _build_summary(
        latest_summary={
            "overdue_batches": {"count": 3},
            "algo": {
                "metrics": {"machine_util_avg": 0.91},
                "candidate_comparison": {
                    "enabled": False,
                    "planned_candidate_count": 3,
                    "completed_candidate_count": 2,
                    "adopted_candidate_key": "graph_w1_of_3",
                    "candidates": [{"candidate_key": "graph_w1_of_3"}],
                },
            },
        }
    )
    cards = {str(card.get("kind")): card for card in summary["risk_cards"]}
    assert cards["candidate_review"]["value"] == "无"
    assert cards["candidate_review"]["severity"] == "ok"
    assert "candidate_review" not in _todo_by_kind(summary)


def test_dashboard_candidate_todo_evidence_assembles_completed_and_baseline_branches() -> None:
    # 候选 evidence_text 多分支组装：基数句 + completed>0 半边 + O25「禁裸删」的
    # baseline_missing_or_failed 半边（经 baseline 缺失路径生产可达）都须如实出现。
    summary = _build_summary()  # 默认 planned=3/completed=2/baseline_missing_or_failed=True/1 候选
    evidence = _todo_by_kind(summary)["candidate_review"]["evidence_text"]
    assert "排产摘要记录了3 套候选方案" in evidence
    assert "其中 2 套已算完" in evidence
    assert "原算法代表方案没有完整结果" in evidence


def test_dashboard_resource_warning_tier_card_and_todo_are_warning() -> None:
    # 中间档 LOAD_WARNING_RATIO(0.75)≤ratio<LOAD_DANGER_RATIO(0.90)：卡片与 todo 两条路径
    # 都应判 warning（既非 danger 也非 ok），此前两路径中间档均无用例。
    summary = _build_summary(
        latest_summary={"overdue_batches": {"count": 3}, "algo": {"metrics": {"machine_util_avg": 0.80}}}
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["resource_overload"]["severity"] == "warning"
    assert cards["resource_overload"]["value"] == "80.0%"
    todo = _todo_by_kind(summary)["resource_overload"]
    assert todo["severity"] == "warning"
    assert "80.0%" in todo["impact_text"]


def test_machine_util_ratio_normalizes_percent_and_rejects_out_of_range() -> None:
    # 百分比归一（>1 且 ≤100→/100）、>100 拒绝、真负值拒绝、bool 拒绝——dashboard 侧此前零覆盖。
    def _s(v: Any) -> Dict[str, Any]:
        return {"algo": {"metrics": {"machine_util_avg": v}}}

    assert _machine_util_ratio(_s(0.5)) == 0.5
    assert _machine_util_ratio(_s(91)) == 0.91  # >1 且 ≤100 → 当百分数归一
    assert _machine_util_ratio(_s(150)) is None  # >100 拒绝（既非比例也非合法百分数）
    assert _machine_util_ratio(_s(-0.1)) is None  # 真负值拒绝
    assert _machine_util_ratio(_s(True)) is None  # bool 拒绝（类型混入）


def test_dashboard_data_gap_plan_time_span_missing_without_error() -> None:
    # 有版本+摘要可用，但 plan_time_span=None 且无 load_error → 「当前计划缺少日期范围」缺口
    # （区别于「计划日期范围暂时读不到」的读取失败态），此分支此前未覆盖。
    summary = _build_summary(plan_time_span=None)
    gap = _todo_by_kind(summary)["data_gap"]
    assert gap["title"] == "当前计划缺少日期范围"
    assert "没有读到有效的计划开始和结束时间" in gap["evidence_text"]


def test_parse_datetime_rejects_garbage_suffix_full_string_match() -> None:
    # 整串匹配（修7，与 _parse_dt 同口径）：坏后缀/非法时间不被截断成合法日期静默当正常时间
    for bad in ("2026-06-01 08:00:00xyz", "坏时间", "2026-06-01 99:99:99"):
        with pytest.raises(ValueError):
            _parse_datetime(bad)
    # 合法格式仍正常解析（兼容斜杠 / T 分隔 / 纯日期）
    assert _parse_datetime("2026-06-01 08:00:00").hour == 8
    assert _parse_datetime("2026/06/01").month == 6
    assert _parse_datetime("2026-06-01T08:00").hour == 8


def test_dashboard_data_gap_flags_unparseable_plan_time_span_range() -> None:
    # plan_time_span 是 dict 但 start/end 无法解析（坏数据）→ 不得通过 isinstance 检查冒充「基础数据完整」，
    # 须落「当前计划缺少日期范围」缺口（与缺日期同语义，禁用需要日期的入口），坏日期不外显。
    for bad_span in (
        {"start_time": "bad-start", "end_time": "bad-end"},  # 无合法日期头
        {"start_time": "2026-06-01 08:00:00xyz", "end_time": "2026-06-02 18:00:00xyz"},  # 合法头+坏后缀（截断陷阱）
    ):
        summary = _build_summary(plan_time_span=bad_span)
        gap = _todo_by_kind(summary)["data_gap"]
        assert gap["title"] == "当前计划缺少日期范围"
        cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
        assert cards["data_gap"]["value"] == "有缺口"
        visible = _visible_text_from_summary(summary)
        # 坏日期既不原样外显、也不得被截断成「2026-06-01」冒充正常进 context_summary（与 data_gap 自洽）
        assert "bad-start" not in visible
        assert "2026-06-01" not in visible


def test_dashboard_overdue_count_rejects_bool_value() -> None:
    # overdue_count=True（bool）：int(True)==1 会伪造「超期 1/danger」→ _nonnegative_count 剔 bool 返回 None，
    # 超期格与统计均落「数据不足」，不冒充正常计数（viewmodel 直调入口也守住，路由侧已另有 bool 守卫）。
    summary = _build_summary(overdue_count=True)
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["overdue_batches"]["value"] == "数据不足"
    assert summary["summary_stats"]["overdue_count_value"] == "数据不足"


def test_dashboard_site_gap_unparseable_start_time_degrades_to_data_insufficient() -> None:
    # 今日计划含无法解析的开始时间（坏数据）→ 现场格不静默跳过坏行冒充「暂未发现/ok」，
    # 而是按「数据不足/notice」诚实降级（与读取失败同语义），且不冒出 site 待办。
    summary = _build_summary(
        today_rows=[
            {"op_id": 201, "start_time": "2026-06-01 08:00:00xyz", "batch_id": "B1"},
            {"op_id": 202, "start_time": "2026-06-01 09:00:00", "batch_id": "B2"},
        ],
        execution_facts_by_op_id={},
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["site_record_gap"]["value"] == "数据不足"
    assert cards["site_record_gap"]["severity"] == "notice"
    assert "site_record_gap" not in _todo_by_kind(summary)
    assert "暂未发现" not in _visible_text_from_summary(summary)


def test_dashboard_candidate_count_rejects_bool_planned_count() -> None:
    # planned_candidate_count=True：bool 不是计数，int(True)==1 会伪造「1 套候选」→ 按类型混入剔除，
    # 无其他权威来源时落「无/ok」、候选待办缺席，不冒充有候选待确认。
    summary = _build_summary(
        latest_summary={
            "overdue_batches": {"count": 3},
            "algo": {
                "metrics": {"machine_util_avg": 0.5},
                "candidate_comparison": {
                    "planned_candidate_count": True,
                    "completed_candidate_count": 0,
                    "candidates": [],
                },
            },
        }
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["candidate_review"]["value"] == "无"
    assert cards["candidate_review"]["severity"] == "ok"
    assert "candidate_review" not in _todo_by_kind(summary)


def test_dashboard_candidate_count_survives_overflow_value_without_crash() -> None:
    # planned_candidate_count=inf：int(float('inf')) 抛 OverflowError，_safe_int 须吞掉降级为 0，
    # 不让首页崩溃；候选数回退到 completed/candidates 等权威字段（修 D）。
    summary = _build_summary(
        latest_summary={
            "overdue_batches": {"count": 3},
            "algo": {
                "metrics": {"machine_util_avg": 0.5},
                "candidate_comparison": {
                    "planned_candidate_count": float("inf"),
                    "completed_candidate_count": 2,
                    "candidates": [{"candidate_key": "graph_w1_of_3"}],
                },
            },
        }
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["candidate_review"]["value"] == "2"  # 回退到 completed=2，未崩溃也未被 inf 污染


def test_dashboard_resource_card_treats_nan_util_as_data_insufficient() -> None:
    # machine_util_avg=NaN（脏摘要）：`nan < 0` 恒 False，旧逻辑会漏过当成正常负荷渲染成
    # 「nan%」/ok 误导。_safe_float 源头剔除非有限值 → 资源负荷格落「数据不足/notice」，
    # 且 resource_overload todo 缺席（ratio=None 不触发负荷风险），可见文本不得泄漏 "nan"。
    summary = _build_summary(
        latest_summary={
            "overdue_batches": {"count": 3},
            "algo": {"metrics": {"machine_util_avg": float("nan")}},
        }
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["resource_overload"]["value"] == "数据不足"
    assert cards["resource_overload"]["severity"] == "notice"
    assert "resource_overload" not in _todo_by_kind(summary)
    assert "nan" not in _visible_text_from_summary(summary).lower()


def test_dashboard_data_gap_cell_warns_when_no_version() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_history=None,
        latest_summary=None,
        latest_summary_parse_state={"parse_failed": False},
        plan_time_span=None,
        today_rows=[],
        execution_facts_by_op_id={},
    )
    cards = {str(card.get("kind")): card for card in summary["risk_cards"]}
    # 无版本→基础数据格 warning「有缺口」；方案待确认摘要不可用→数据不足/notice
    assert cards["data_gap"]["severity"] == "warning"
    assert cards["data_gap"]["value"] == "有缺口"
    assert cards["candidate_review"]["value"] == "数据不足"


def test_dashboard_six_cell_consistent_when_summary_empty_dict() -> None:
    # 空摘要 {}（_has_current_summary 判不可用）：超期/方案待确认均「数据不足」时，
    # 基础数据格须同口径显「有缺口/warning」而非「完整/ok」，6 格不自相矛盾（codex 维度4 修复）
    summary = _build_summary(
        latest_summary={},
        navigation_context={"version": "12", "plan_role": "adopted"},
        today_rows=[],
        execution_facts_by_op_id={},
    )
    cards = {str(c.get("kind")): c for c in summary["risk_cards"]}
    assert cards["overdue_batches"]["value"] == "数据不足"
    assert cards["candidate_review"]["value"] == "数据不足"
    assert cards["data_gap"]["value"] == "有缺口"
    assert cards["data_gap"]["severity"] == "warning"


def test_dashboard_workbench_does_not_guess_write_or_empty_summary_values() -> None:
    summary = _build_summary(
        latest_summary={},
        navigation_context={"version": "12", "plan_role": "adopted"},
        today_rows=[],
        execution_facts_by_op_id={},
    )
    cards = {str(item.get("kind")): item for item in summary.get("risk_cards") or []}

    assert summary["latest_plan"]["can_write_feedback"] is False
    assert summary["summary_stats"]["overdue_count_value"] == "数据不足"
    assert cards["overdue_batches"]["value"] == "数据不足"
    assert cards["site_record_gap"]["value"] == "数据不足"
    assert "暂未发现" not in _visible_text_from_summary(summary)

    valid_zero = _build_summary(latest_summary={"overdue_batches": {"count": 0}, "algo": {"metrics": {"machine_util_avg": 0}}}, overdue_count=0)
    assert valid_zero["summary_stats"]["overdue_count_value"] == "0"
    assert {str(item.get("kind")): item for item in valid_zero["risk_cards"]}["overdue_batches"]["value"] == "0"


def test_dashboard_workbench_does_not_turn_site_fact_load_error_into_no_gap() -> None:
    summary = _build_summary(execution_facts_load_error="现场执行事实读取失败")
    cards = {str(item.get("kind")): item for item in summary.get("risk_cards") or []}
    todos = _todo_by_kind(summary)

    assert cards["site_record_gap"]["value"] == "数据不足"
    assert "现场事实暂时读不到" in cards["site_record_gap"]["helper_text"]
    assert todos["data_gap"]["title"] == "现场情况暂时读不到"
    assert "暂未发现" not in _visible_text_from_summary(summary)


def test_dashboard_workbench_summary_links_keep_request_batch_and_resource_context() -> None:
    summary = _build_summary(
        navigation_context={
            "version": "12",
            "plan_role": "adopted",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "is_current_executable_official_version": True,
            "can_write_feedback": True,
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "resource_type": "machine",
            "resource_id": "M-RPT",
            "resource_label": "一号设备",
        }
    )
    todos = _todo_by_kind(summary)

    overdue_url = todos["overdue"]["primary_action"]["url"]
    utilization_url = todos["resource_overload"]["secondary_action"]["url"]
    dispatch_url = todos["resource_overload"]["primary_action"]["url"]
    review_url = todos["site_record_gap"]["primary_action"]["url"]

    assert _query(overdue_url) == {
        "version": ["12"],
        "plan_role": ["adopted"],
        "date_from": ["2026-05-06"],
        "date_to": ["2026-05-06"],
        "batch_id": ["B-RPT"],
        "resource_type": ["machine"],
        "resource_id": ["M-RPT"],
    }
    assert _query(utilization_url) == {
        "version": ["12"],
        "plan_role": ["adopted"],
        "start_date": ["2026-05-06"],
        "end_date": ["2026-05-06"],
        "batch_id": ["B-RPT"],
        "resource_type": ["machine"],
        "resource_id": ["M-RPT"],
    }
    assert _query(dispatch_url) == {
        "version": ["12"],
        "plan_role": ["adopted"],
        "date_from": ["2026-05-06"],
        "date_to": ["2026-05-06"],
        "period_preset": ["custom"],
        "scope_type": ["machine"],
        "scope_id": ["M-RPT"],
        "machine_id": ["M-RPT"],
        "batch_id": ["B-RPT"],
    }
    assert _query(review_url) == {
        "version": ["12"],
        "plan_role": ["adopted"],
        "date_from": ["2026-05-06"],
        "date_to": ["2026-05-06"],
        "batch_id": ["B-RPT"],
        "resource_type": ["machine"],
        "resource_id": ["M-RPT"],
    }


def test_dashboard_workbench_summary_respects_requested_non_adopted_plan_identity() -> None:
    summary = _build_summary(
        navigation_context={
            "version": "12",
            "plan_role": "baseline_best",
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "resource_type": "machine",
            "resource_id": "M-RPT",
        }
    )
    todos = _todo_by_kind(summary)
    review_action = todos["site_record_gap"]["primary_action"]
    analysis_query = _query(todos["candidate_review"]["primary_action"]["url"])

    assert analysis_query["version"] == ["12"]
    assert analysis_query["plan_role"] == ["baseline_best"]
    assert review_action["disabled"] is True
    assert review_action["url"] == ""
    assert "只复盘正式采用方案" in review_action["disabled_reason"]
    visible_text = _visible_text_from_summary(summary)
    assert "最新正式采用方案" not in visible_text
    assert "最新排产摘要" not in visible_text
    assert "按正式采用方案" not in visible_text


def test_dashboard_workbench_summary_keeps_superseded_adopted_review_disabled() -> None:
    summary = _build_summary(
        navigation_context={
            "version": "12",
            "plan_role": "adopted",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "is_superseded_by_newer_version": True,
            "can_write_feedback": False,
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
            "batch_id": "B-RPT",
            "resource_type": "machine",
            "resource_id": "M-RPT",
        }
    )
    todos = _todo_by_kind(summary)
    review_action = todos["site_record_gap"]["primary_action"]
    analysis_query = _query(todos["candidate_review"]["primary_action"]["url"])

    assert analysis_query["version"] == ["12"]
    assert analysis_query["plan_role"] == ["adopted"]
    assert review_action["disabled"] is True
    assert review_action["url"] == ""
    assert "历史正式方案" in review_action["disabled_reason"]
    visible_text = _visible_text_from_summary(summary)
    assert "最新正式采用方案" not in visible_text
    assert "最新排产摘要" not in visible_text
    assert "按正式采用方案" not in visible_text


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
    assert cards["overdue_batches"]["value"] == "数据不足"
    assert "不能把缺失的超期统计显示成 0" in cards["overdue_batches"]["helper_text"]
    assert cards["resource_overload"]["value"] == "数据不足"
    assert cards["resource_overload"]["value"] != "0%"
    assert "当前没有必须马上处理的排产风险" in summary["empty_state"]
    visible_text = _visible_text_from_summary(summary)
    assert "最新计划" not in visible_text
    assert "最新排产历史" not in visible_text


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
    assert todos["data_gap"]["title"] == "当前排产摘要读取失败"
    assert "页面仅展示基础历史信息" in todos["data_gap"]["evidence_text"]
    cards = {str(item.get("kind")): item for item in summary.get("risk_cards") or []}
    assert cards["overdue_batches"]["value"] == "数据不足"


def test_dashboard_workbench_plan_time_span_failure_is_visible_instead_of_missing_dates() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_summary={
            "overdue_batches": {"count": 0},
            "algo": {"metrics": {"machine_util_avg": 0.2}},
        },
        plan_time_span=None,
        plan_time_span_load_error="计划日期范围读取失败，首页暂时不能判断甘特、资源派工和报表需要的日期。",
        navigation_context={
            "version": "12",
            "plan_role": "adopted",
            "requested_plan_role": "adopted",
            "effective_plan_role": "adopted",
            "is_current_executable_official_version": True,
            "can_write_feedback": True,
            "date_from": "2026-05-06",
            "date_to": "2026-05-06",
        },
        today_rows=[],
        execution_facts_by_op_id={},
    )
    todos = _todo_by_kind(summary)
    quick_links = {link["target_page"]: link for link in summary["quick_links"]}

    assert set(todos) == {"data_gap"}
    assert todos["data_gap"]["title"] == "计划日期范围暂时读不到"
    assert "读取失败" in todos["data_gap"]["evidence_text"]
    assert "误当成没有日期" in todos["data_gap"]["impact_text"]
    assert quick_links["gantt"]["disabled"] is True
    assert quick_links["gantt"]["url"] == ""
    assert "读取失败" in quick_links["gantt"]["disabled_reason"]
    assert "2026-05-06" not in quick_links["gantt"]["context_summary"]


def test_dashboard_workbench_execution_fact_failure_does_not_fake_site_gap() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_summary={
            "overdue_batches": {"count": 0},
            "algo": {"metrics": {"machine_util_avg": 0.2}},
        },
        execution_facts_by_op_id={},
        execution_facts_load_error="现场执行事实读取失败，首页暂时不能判断哪些任务现场情况待确认。",
    )
    todos = _todo_by_kind(summary)

    assert "site_record_gap" not in todos
    assert set(todos) == {"data_gap"}
    assert todos["data_gap"]["title"] == "现场情况暂时读不到"
    assert "避免把读取失败误当成现场没有反馈" in todos["data_gap"]["impact_text"]


def test_dashboard_workbench_today_rows_failure_does_not_fake_empty_site_gap() -> None:
    summary = _build_summary(
        overdue_count=0,
        latest_summary={
            "overdue_batches": {"count": 0},
            "algo": {"metrics": {"machine_util_avg": 0.2}},
        },
        today_rows=[],
        execution_facts_by_op_id={},
        today_rows_load_error="今日正式计划读取失败，首页暂时不能判断哪些任务现场情况待确认。",
    )
    todos = _todo_by_kind(summary)

    assert "site_record_gap" not in todos
    assert set(todos) == {"data_gap"}
    assert todos["data_gap"]["title"] == "今日计划暂时读不到"
    assert "避免把读取失败误当成没有待确认" in todos["data_gap"]["impact_text"]


def test_visible_text_parser_helper_ignores_href_query_internal_fields() -> None:
    parser = _VisibleTextParser()
    parser.feed('<a href="/x?plan_role=adopted&op_id=1"><span>查看排产分析</span></a>')
    assert "plan_role" not in "\n".join(parser.parts)
    assert "op_id" not in "\n".join(parser.parts)
