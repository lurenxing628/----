"""回归测试：排产优化分析页（scheduler_analysis_vm + analysis.html）的可观测性与兼容口径——旧 summary 缺 dispatch_mode/rule 不合成「-」、不暴露 comparison_metric/best_score_schema/算法方案标签等内部术语而显示中文兼容提示；新 summary 透传裁剪提示/warning 预览与隐藏计数/停机与冻结窗口降级提示/数据异常与未排批次卡片差值；读侧回退场景仍展示卡片值但缺上一版字段时不显差值；含私有路径的内部诊断单列为「维护诊断」不计入业务提醒、不泄露 sqlite 细节。"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

from tests._support.paths import REPO_ROOT
from web.viewmodels.scheduler_summary_display import build_summary_display_state


def make_metrics(*, overdue_count: int, invalid_due_count: int = 0, unscheduled_batch_count: int = 0) -> Dict[str, Any]:
    return {
        "overdue_count": int(overdue_count),
        "invalid_due_count": int(invalid_due_count),
        "unscheduled_batch_count": int(unscheduled_batch_count),
        "total_tardiness_hours": 5.0,
        "weighted_tardiness_hours": 3.0,
        "makespan_hours": 100.0,
        "makespan_internal_hours": 80.0,
        "changeover_count": 1,
        "machine_util_avg": 0.6,
        "machine_used_count": 3,
        "machine_load_cv": 0.1,
        "operator_util_avg": 0.5,
        "operator_used_count": 2,
        "operator_load_cv": 0.2,
    }


def make_legacy_metrics(*, overdue_count: int) -> Dict[str, Any]:
    legacy_metrics = dict(make_metrics(overdue_count=overdue_count))
    legacy_metrics.pop("invalid_due_count", None)
    legacy_metrics.pop("unscheduled_batch_count", None)
    return legacy_metrics


def make_old_summary() -> Dict[str, Any]:
    return {
        "version": 1,
        "algo": {
            "objective": "min_overdue",
            "metrics": make_legacy_metrics(overdue_count=2),
            "attempts": [
                {
                    "tag": "start:priority_first|batch_order:slack",
                    "strategy": "priority_first",
                    "failed_ops": 0,
                    "score": [0, 2],
                    "metrics": {"overdue_count": 2},
                }
            ],
            "improvement_trace": [],
        },
        "time_cost_ms": 123,
    }


def make_prev_summary() -> Dict[str, Any]:
    return {
        "version": 1,
        "invalid_due_count": 5,
        "unscheduled_batch_count": 8,
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "comparison_metric": "overdue_count",
            "time_budget_seconds": 20,
            "metrics": make_metrics(overdue_count=4, invalid_due_count=5, unscheduled_batch_count=8),
            "attempts": [
                {
                    "tag": "start:priority_first|sgs:cr",
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "score": [0, 4],
                    "metrics": {"overdue_count": 4},
                }
            ],
            "improvement_trace": [],
        },
        "time_cost_ms": 222,
    }


def make_new_summary() -> Dict[str, Any]:
    return {
        "version": 2,
        "summary_truncated": True,
        "original_size_bytes": 600000,
        "invalid_due_count": 2,
        "unscheduled_batch_count": 3,
        "warnings": [
            "冻结窗口存在跳批风险",
            "停机区间加载失败，本次先按常规能力继续",
            "存在 1 个批次未命中首选技能",
            "开始时间已规范化为：2026-05-19 08:00:00",
        ],
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "comparison_metric": "overdue_count",
            "time_budget_seconds": 20,
            "metrics": make_metrics(overdue_count=1, invalid_due_count=2, unscheduled_batch_count=3),
            "attempts": [
                {
                    "source_label": "多起点方案",
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "score": [0, 1],
                    "metrics": {"overdue_count": 1},
                }
            ],
            "improvement_trace": [],
            "downtime_avoid": {
                "loaded_ok": False,
                "degraded": True,
                "degradation_reason": "停机区间加载失败",
                "extend_attempted": False,
            },
            "freeze_window": {
                "enabled": "yes",
                "days": 3,
                "frozen_op_count": 4,
                "frozen_batch_count": 7,
                "frozen_batch_ids_sample": ["B001", "B002", "B003", "B004", "B005", "B006", "B007"],
                "freeze_state": "degraded",
                "freeze_applied": False,
                "freeze_degradation_codes": ["freeze_skipped_batch"],
                "degraded": True,
                "degradation_reason": "【冻结窗口】跳过批次 B001",
            },
            "best_score_schema": [
                {"index": 0, "key": "failed_ops", "label": "失败工序数"},
                {"index": 1, "key": "overdue_count", "label": "超期批次数"},
            ],
            "config_snapshot": {
                "sort_strategy": "priority_first",
                "dispatch_mode": "sgs",
                "dispatch_rule": "cr",
                "objective": "min_overdue",
                "time_budget_seconds": 20,
            },
        },
        "degradation_events": [
            {
                "code": "downtime_avoid_degraded",
                "scope": "schedule.summary.downtime_avoid",
                "field": "downtime_avoid",
                "message": "停机区间加载失败",
                "count": 1,
            },
            {
                "code": "freeze_window_degraded",
                "scope": "schedule.summary.freeze_window",
                "field": "freeze_window",
                "message": "【冻结窗口】跳过批次 B001",
                "count": 1,
            },
        ],
        "degradation_counters": {"downtime_avoid_degraded": 1, "freeze_window_degraded": 1},
        "time_cost_ms": 456,
    }


def make_top_level_fallback_summary() -> Dict[str, Any]:
    fallback_metrics = dict(make_metrics(overdue_count=1, invalid_due_count=9, unscheduled_batch_count=6))
    fallback_metrics.pop("invalid_due_count", None)
    fallback_metrics.pop("unscheduled_batch_count", None)
    return {
        "version": 3,
        "invalid_due_count": 4,
        "unscheduled_batch_count": 2,
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "comparison_metric": "overdue_count",
            "time_budget_seconds": 20,
            "metrics": fallback_metrics,
            "attempts": [
                {
                    "tag": "start:priority_first|sgs:cr",
                    "strategy": "priority_first",
                    "dispatch_mode": "sgs",
                    "dispatch_rule": "cr",
                    "failed_ops": 0,
                    "score": [0, 1],
                    "metrics": {"overdue_count": 1},
                }
            ],
            "improvement_trace": [],
        },
        "time_cost_ms": 321,
    }


def build_case_inputs(*, version: int, summary_obj: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    result_summary_json = json.dumps(summary_obj, ensure_ascii=False)
    selected = {
        "version": int(version),
        "schedule_time": f"2026-01-0{version} 08:00:00",
        "strategy": "priority_first",
        "result_status": "success",
        "created_by": "reg",
        "result_summary": result_summary_json,
    }
    return selected, {"version": int(version), "result_summary": result_summary_json}




def card_by_key(ctx: Dict[str, Any], key: str) -> Dict[str, Any]:
    for card in list(ctx.get("extra_cards") or []):
        if card.get("key") == key:
            return card
    raise AssertionError(f"未找到卡片：{key}")


def test_scheduler_analysis_observability(app_client) -> None:
    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    assert not (REPO_ROOT / "templates/scheduler/analysis.html").exists()
    assert not (REPO_ROOT / "templates/components/ui_macros.html").exists()

    old_summary = make_old_summary()
    old_selected, old_hist = build_case_inputs(version=1, summary_obj=old_summary)
    old_ctx = build_analysis_context(selected_ver=1, raw_hist=[old_hist], selected_item=old_selected)
    assert old_ctx.get("attempts"), "旧 summary 应提取出 attempts"
    assert old_ctx["attempts"][0].get("dispatch_mode") == "", "旧 summary 缺少 dispatch_mode 时不应合成 '-'"
    assert old_ctx["attempts"][0].get("dispatch_rule") == "", "旧 summary 缺少 dispatch_rule 时不应合成 '-'"
    assert not old_ctx.get("extra_cards"), "旧 summary 不应生成数据异常/未排批次卡片"
    assert old_ctx.get("freeze_display") is None, "旧 summary 不应生成冻结摘要"

    assert old_ctx["compat_fallback"]["used"] is True
    assert "优化对比指标" in old_ctx["compat_fallback"]["missing_field_labels"]
    assert "系统比较顺序" in old_ctx["compat_fallback"]["missing_field_labels"]
    assert old_ctx["attempts"][0]["display_tag"] == "方案 1"
    assert "start:priority_first|batch_order:slack" not in old_ctx["attempts"][0]["display_tag"]
    old_display = build_summary_display_state(old_ctx["selected_summary"], result_status="success")
    assert old_display["summary_truncated"] is False
    assert old_ctx["summary_degradation_messages"] == []

    prev_summary = make_prev_summary()
    _prev_selected, prev_hist = build_case_inputs(version=1, summary_obj=prev_summary)
    new_summary = make_new_summary()
    new_selected, new_hist = build_case_inputs(version=2, summary_obj=new_summary)
    new_ctx = build_analysis_context(selected_ver=2, raw_hist=[prev_hist, new_hist], selected_item=new_selected)
    assert new_ctx.get("attempts"), "新 summary 应提取出 attempts"
    assert new_ctx["attempts"][0].get("dispatch_mode") == "sgs", "dispatch_mode 未从展示态透传"
    assert new_ctx["attempts"][0].get("dispatch_rule") == "cr", "dispatch_rule 未从展示态透传"
    selected_summary = new_ctx.get("selected_summary") or {}
    assert bool(selected_summary.get("summary_truncated")), "selected_summary 未保留 summary_truncated"
    assert int(selected_summary.get("original_size_bytes") or 0) == 600000, "selected_summary 未保留 original_size_bytes"
    assert bool(((selected_summary.get("algo") or {}).get("downtime_avoid") or {}).get("degraded")), "停机降级字段丢失"
    assert bool(((selected_summary.get("algo") or {}).get("freeze_window") or {}).get("degraded")), "冻结窗口降级字段丢失"

    data_issue_card = card_by_key(new_ctx, "invalid_due_count")
    unscheduled_card = card_by_key(new_ctx, "unscheduled_batch_count")
    assert int(data_issue_card.get("value") or 0) == 2, "数据异常卡片当前值错误"
    assert int(data_issue_card.get("delta") or 0) == -3, "数据异常卡片差值错误"
    assert int(unscheduled_card.get("value") or 0) == 3, "未排批次卡片当前值错误"
    assert int(unscheduled_card.get("delta") or 0) == -5, "未排批次卡片差值错误"

    freeze_display = new_ctx.get("freeze_display") or {}
    assert bool(freeze_display.get("enabled")), "冻结摘要应识别 yes 字符串为启用"
    assert freeze_display.get("state") == "degraded", "冻结摘要状态错误"
    assert freeze_display.get("state_label") == "部分未生效", "冻结摘要中文状态错误"
    assert bool(freeze_display.get("degraded")), "冻结摘要降级标记错误"
    assert int(freeze_display.get("frozen_op_count") or 0) == 4, "冻结工序数错误"
    assert int(freeze_display.get("frozen_batch_count") or 0) == 7, "冻结批次数错误"
    assert list(freeze_display.get("sample_batches") or []) == ["B001", "B002", "B003", "B004", "B005"], "冻结示例批次未截断到前 5 个"
    assert int(freeze_display.get("sample_more_count") or 0) == 2, "冻结示例批次剩余数量错误"
    summary_degradation_messages = list(new_ctx.get("summary_degradation_messages") or [])
    assert any(item.get("code") == "downtime_avoid_degraded" for item in summary_degradation_messages), summary_degradation_messages
    assert any(item.get("code") == "freeze_window_degraded" for item in summary_degradation_messages), summary_degradation_messages

    new_display = build_summary_display_state(new_ctx["selected_summary"], result_status="success")
    assert new_display["summary_truncated"] is True
    assert new_ctx["selected_summary"]["original_size_bytes"] == 600000
    assert new_display["warning_total"] == 4 and new_display["warning_hidden_count"] == 1
    assert len(new_display["warnings_preview"]) == 3
    assert "开始时间已规范化为：2026-05-19 08:00:00" not in new_display["warnings_preview"]
    public_degradation = json.dumps(new_ctx["display_summary_degradation_messages"], ensure_ascii=False)
    assert "【冻结窗口】跳过批次 B001" not in public_degradation
    assert new_ctx["attempts"][0]["display_tag"] == "多起点方案"
    assert "start:priority_first|sgs:cr" not in new_ctx["attempts"][0]["display_tag"]
    assert {card["label"] for card in new_ctx["extra_cards"]} == {"数据异常批次数", "未排批次数"}

    fallback_summary = make_top_level_fallback_summary()
    fallback_selected, fallback_hist = build_case_inputs(version=3, summary_obj=fallback_summary)
    fallback_ctx = build_analysis_context(selected_ver=3, raw_hist=[old_hist, fallback_hist], selected_item=fallback_selected)
    fallback_selected_metrics = fallback_ctx.get("selected_metrics") or {}
    assert "invalid_due_count" not in fallback_selected_metrics, "回退用例不应从 algo.metrics 直接命中数据异常字段"
    assert "unscheduled_batch_count" not in fallback_selected_metrics, "回退用例不应从 algo.metrics 直接命中未排批次字段"

    fallback_data_issue_card = card_by_key(fallback_ctx, "invalid_due_count")
    fallback_unscheduled_card = card_by_key(fallback_ctx, "unscheduled_batch_count")
    assert int(fallback_data_issue_card.get("value") or 0) == 4, "读侧回退后数据异常卡片值错误"
    assert fallback_data_issue_card.get("delta") is None, "上一版缺少数据异常字段时不应展示差值"
    assert int(fallback_unscheduled_card.get("value") or 0) == 2, "读侧回退后未排批次卡片值错误"
    assert fallback_unscheduled_card.get("delta") is None, "上一版缺少未排批次字段时不应展示差值"

    assert {card["label"] for card in fallback_ctx["extra_cards"]} == {"数据异常批次数", "未排批次数"}

    private_warning_summary = {
        "version": 4,
        "warnings": ["sqlite OperationalError: /Users/private/aps.db locked"],
        "algo": {"metrics": make_metrics(overdue_count=0)},
    }
    private_warning_selected, private_warning_hist = build_case_inputs(version=4, summary_obj=private_warning_summary)
    private_warning_ctx = build_analysis_context(
        selected_ver=4,
        raw_hist=[private_warning_hist],
        selected_item=private_warning_selected,
    )
    private_display = build_summary_display_state(private_warning_ctx["selected_summary"], result_status="success")
    assert private_display["warning_total"] == 0
    assert private_display["maintenance_diagnostic_count"] == 1
    assert private_display["warnings_preview"] == [] and private_display["warning_hidden_count"] == 0
    assert "sqlite" not in json.dumps(private_display, ensure_ascii=False)
