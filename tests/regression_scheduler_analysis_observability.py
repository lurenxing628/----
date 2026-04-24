from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any, Dict, Tuple


def find_repo_root() -> str:
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, ".."))
    if os.path.exists(os.path.join(repo_root, "app.py")) and os.path.exists(os.path.join(repo_root, "schema.sql")):
        return repo_root
    raise RuntimeError("未找到项目根目录：要求存在 app.py 与 schema.sql")


def setup_runtime(repo_root: str) -> None:
    tmpdir = tempfile.mkdtemp(prefix="aps_reg_analysis_observability_")
    os.environ["APS_ENV"] = "development"
    os.environ["APS_DB_PATH"] = os.path.join(tmpdir, "aps.db")
    os.environ["APS_LOG_DIR"] = os.path.join(tmpdir, "logs")
    os.environ["APS_BACKUP_DIR"] = os.path.join(tmpdir, "backups")
    os.environ["APS_EXCEL_TEMPLATE_DIR"] = os.path.join(tmpdir, "templates_excel")
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)


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
            "停机区间加载失败，已按默认能力继续",
            "存在 1 个批次未命中首选技能",
            "另有告警需要在系统历史查看",
        ],
        "algo": {
            "mode": "improve",
            "objective": "min_overdue",
            "comparison_metric": "overdue_count",
            "time_budget_seconds": 20,
            "metrics": make_metrics(overdue_count=1, invalid_due_count=2, unscheduled_batch_count=3),
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


def render_analysis_html(app, render_template, *, version: int, selected: Dict[str, Any], ctx: Dict[str, Any]) -> str:
    from web.viewmodels.scheduler_summary_display import build_summary_display_state

    with app.test_request_context(f"/scheduler/analysis?version={version}"):
        return render_template(
            "scheduler/analysis.html",
            title="regression",
            ui_mode="v1",
            versions=[
                {
                    "version": int(version),
                    "schedule_time": selected["schedule_time"],
                    "strategy": selected["strategy"],
                    "result_status": selected["result_status"],
                }
            ],
            selected_summary_display=build_summary_display_state(
                ctx.get("selected_summary"),
                result_status=(ctx.get("selected") or {}).get("result_status"),
                parse_state=(ctx.get("selected") or {}).get("result_summary_parse_state"),
            ),
            trend_summary_state={"incomplete": False, "parse_failed_count": 0},
            **ctx,
        )


def card_by_key(ctx: Dict[str, Any], key: str) -> Dict[str, Any]:
    for card in list(ctx.get("extra_cards") or []):
        if card.get("key") == key:
            return card
    raise AssertionError(f"未找到卡片：{key}")


def main() -> None:
    repo_root = find_repo_root()
    setup_runtime(repo_root)

    from flask import render_template

    from app import create_app
    from web.viewmodels.scheduler_analysis_vm import build_analysis_context

    app = create_app()

    old_summary = make_old_summary()
    old_selected, old_hist = build_case_inputs(version=1, summary_obj=old_summary)
    old_ctx = build_analysis_context(selected_ver=1, raw_hist=[old_hist], selected_item=old_selected)
    assert old_ctx.get("attempts"), "旧 summary 应提取出 attempts"
    assert old_ctx["attempts"][0].get("dispatch_mode") == "-", "旧 summary 的 dispatch_mode 应安全回退为 '-'"
    assert old_ctx["attempts"][0].get("dispatch_rule") == "-", "旧 summary 的 dispatch_rule 应安全回退为 '-'"
    assert not old_ctx.get("extra_cards"), "旧 summary 不应生成数据异常/未排批次卡片"
    assert old_ctx.get("freeze_display") is None, "旧 summary 不应生成冻结摘要"

    old_html = render_analysis_html(app, render_template, version=1, selected=old_selected, ctx=old_ctx)
    assert "排产优化分析" in old_html, "旧 summary 页面未成功渲染"
    assert "裁剪后摘要" not in old_html, "旧 summary 不应展示裁剪提示"
    assert "停机避让约束已降级" not in old_html, "旧 summary 不应展示停机降级提示"
    assert "冻结窗口约束已降级" not in old_html, "旧 summary 不应展示冻结窗口降级提示"
    assert "-/-" in old_html, "旧 summary 的 attempts 派工列应展示安全回退值"
    assert 'stat-card-label">数据异常批次数</div>' not in old_html, "旧 summary 不应展示数据异常卡片"
    assert 'stat-card-label">未排批次数</div>' not in old_html, "旧 summary 不应展示未排批次卡片"
    assert "冻结工序数：" not in old_html, "旧 summary 不应展示冻结摘要"

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
    assert freeze_display.get("state_label") == "已降级", "冻结摘要中文状态错误"
    assert bool(freeze_display.get("degraded")), "冻结摘要降级标记错误"
    assert int(freeze_display.get("frozen_op_count") or 0) == 4, "冻结工序数错误"
    assert int(freeze_display.get("frozen_batch_count") or 0) == 7, "冻结批次数错误"
    assert list(freeze_display.get("sample_batches") or []) == ["B001", "B002", "B003", "B004", "B005"], "冻结示例批次未截断到前 5 个"
    assert int(freeze_display.get("sample_more_count") or 0) == 2, "冻结示例批次剩余数量错误"
    summary_degradation_messages = list(new_ctx.get("summary_degradation_messages") or [])
    assert any(item.get("code") == "downtime_avoid_degraded" for item in summary_degradation_messages), summary_degradation_messages
    assert any(item.get("code") == "freeze_window_degraded" for item in summary_degradation_messages), summary_degradation_messages

    new_html = render_analysis_html(app, render_template, version=2, selected=new_selected, ctx=new_ctx)
    assert "当前展示为裁剪后摘要" in new_html, "未展示 summary_truncated 提示"
    assert "600000" in new_html, "未展示 original_size_bytes"
    assert "告警：4 条" in new_html, "未展示 warning_total"
    assert "冻结窗口存在跳批风险" in new_html, "未展示 warnings_preview"
    assert "停机区间加载失败，已按默认能力继续" in new_html, "未展示第二条 warnings_preview"
    assert "存在 1 个批次未命中首选技能" in new_html, "未展示第三条 warnings_preview"
    assert "另有 1 条告警，请到系统历史查看。" in new_html, "未展示 warning_hidden_count"
    assert "另有告警需要在系统历史查看" not in new_html, "第 4 条 warning 不应出现在 preview 中"
    assert "停机避让约束已降级" in new_html, "未展示停机降级提示"
    assert "停机区间加载失败" in new_html, "未展示停机降级原因"
    assert "冻结窗口约束已降级" in new_html, "未展示冻结窗口降级提示"
    assert "【冻结窗口】跳过批次 B001" not in new_html, "不应展示冻结窗口内部降级明细"
    assert 'stat-card-label">数据异常批次数</div>' in new_html, "未展示数据异常卡片"
    assert 'stat-card-label">未排批次数</div>' in new_html, "未展示未排批次卡片"
    assert "对比上一版：-3" in new_html, "未展示数据异常对比差值"
    assert "对比上一版：-5" in new_html, "未展示未排批次对比差值"
    assert "当前状态：已降级" in new_html, "未展示冻结状态标签"
    assert "冻结工序数：4" in new_html, "未展示冻结工序数"
    assert "冻结批次数：7" in new_html, "未展示冻结批次数"
    assert "示例批次：B001、B002、B003、B004、B005" in new_html, "未展示冻结示例批次"
    assert "及其他 2 个…" in new_html, "未展示冻结示例批次剩余数量"
    assert "排序策略" in new_html, "attempts 表头未更正为排序策略"
    assert "派工" in new_html, "attempts 表头未新增派工列"
    assert "sgs/cr" in new_html, "attempts 派工列未闭环展示 dispatch_mode/dispatch_rule"

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

    fallback_html = render_analysis_html(app, render_template, version=3, selected=fallback_selected, ctx=fallback_ctx)
    assert 'stat-card-label">数据异常批次数</div>' in fallback_html, "读侧回退场景未展示数据异常卡片"
    assert 'stat-card-label">未排批次数</div>' in fallback_html, "读侧回退场景未展示未排批次卡片"

    print("OK")


if __name__ == "__main__":
    main()
