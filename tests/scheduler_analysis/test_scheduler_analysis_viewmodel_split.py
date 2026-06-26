"""回归测试：排产分析 viewmodel 拆分为 freeze/metrics/overview 子模块后，build_analysis_context 仍产出完整且可 JSON 序列化的上下文（含 metric_cards/extra_cards/freeze_display/best_score_schema_display/analysis_labels 等全部键）、对比上一版算 delta，旧 summary 缺字段时 compat_fallback.used=True 并列出缺失标签，且对 Infinity/NaN/1e9999/空串/布尔等不可信数值统一显示无法安全展示而非误转为 0；拆出的 extract_metrics_from_summary/build_extra_cards/build_freeze_display/build_analysis_labels 保持独立可用。"""

from __future__ import annotations

import json

from web.viewmodels.scheduler_analysis_freeze import build_freeze_display
from web.viewmodels.scheduler_analysis_metrics import build_extra_cards, extract_metrics_from_summary
from web.viewmodels.scheduler_analysis_overview import build_analysis_labels
from web.viewmodels.scheduler_analysis_vm import build_analysis_context, safe_float


def _selected_summary() -> dict:
    return {
        "time_cost_ms": 321,
        "invalid_due_count": 2,
        "unscheduled_batch_count": 1,
        "algo": {
            "objective": "min_tardiness",
            "comparison_metric": "total_tardiness_hours",
            "best_score_schema": [
                {"index": 0, "key": "failed_ops", "label": "失败工序数"},
                {"index": 1, "key": "total_tardiness_hours"},
            ],
            "metrics": {
                "overdue_count": 4,
                "total_tardiness_hours": 9.5,
                "weighted_tardiness_hours": 11.0,
                "makespan_hours": 32.0,
                "makespan_internal_hours": 25.0,
                "changeover_count": 3,
            },
            "freeze_window": {
                "enabled": "yes",
                "freeze_applied": True,
                "freeze_state": "degraded",
                "days": 2,
                "frozen_op_count": 4,
                "frozen_batch_count": 7,
                "frozen_batch_ids_sample": ["B001", "B002", "B003", "B004", "B005", "B006"],
                "degraded": True,
                "degradation_reason": "示例原因",
            },
            "config_snapshot": {
                "objective": "min_tardiness",
                "sort_strategy": "fifo",
                "dispatch_mode": "sgs",
                "dispatch_rule": "slack",
                "time_budget_seconds": 10,
            },
        },
    }


def test_analysis_viewmodel_split_preserves_context_payload() -> None:
    prev_summary = {
        "algo": {
            "metrics": {
                "overdue_count": 1,
                "total_tardiness_hours": 4.5,
                "weighted_tardiness_hours": 5.0,
                "makespan_hours": 20.0,
                "makespan_internal_hours": 18.0,
                "changeover_count": 1,
            }
        },
        "invalid_due_count": 1,
        "unscheduled_batch_count": 0,
    }
    summary = _selected_summary()

    ctx = build_analysis_context(
        selected_ver=7,
        raw_hist=[
            {"version": 6, "result_summary": prev_summary},
            {"version": 7, "result_summary": summary},
        ],
        selected_item={"version": 7, "result_summary": summary},
    )

    expected_keys = {
        "selected",
        "selected_summary",
        "selected_metrics",
        "prev_metrics",
        "objective_key",
        "algo_objective_label",
        "best_score_schema_display",
        "compat_fallback",
        "candidate_comparison_display",
        "diagnostic_sections",
        "analysis_labels",
        "algo_config_snapshot_objective_label",
        "objective_key_label",
        "objective_choice_labels",
        "attempts",
        "trace_chart",
        "trend_rows",
        "trend_charts",
        "extra_cards",
        "freeze_display",
        "summary_degradation_messages",
        "display_summary_degradation_messages",
        "metric_cards",
    }
    assert expected_keys <= set(ctx)
    assert ctx["selected_metrics"]["overdue_count"] == 4
    assert ctx["prev_metrics"]["overdue_count"] == 1
    assert ctx["extra_cards"] == [
        {"key": "invalid_due_count", "label": "数据异常批次数", "value": 2, "delta": None, "type_class": "type-info"},
        {"key": "unscheduled_batch_count", "label": "未排批次数", "value": 1, "delta": None, "type_class": ""},
    ]
    assert ctx["metric_cards"][0]["value"] == "4"
    assert ctx["metric_cards"][0]["delta"] == "对比上一版：+3"
    assert ctx["freeze_display"]["state_label"] == "部分未生效"
    assert ctx["freeze_display"]["sample_batches"] == ["B001", "B002", "B003", "B004", "B005"]
    assert ctx["freeze_display"]["sample_more_count"] == 2
    assert ctx["compat_fallback"]["used"] is False
    assert ctx["best_score_schema_display"][1]["display_label"] == "总拖期小时"
    assert ctx["analysis_labels"]["dispatch_mode"]["sgs"] == "智能派工"
    assert ctx["analysis_labels"]["dispatch_rule"]["slack"] == "时间余量少的先做"
    assert safe_float("3.5") == 3.5
    json.dumps(ctx, ensure_ascii=False)


def test_split_helpers_keep_standalone_behavior() -> None:
    summary = _selected_summary()
    metrics = extract_metrics_from_summary(summary)

    assert metrics and metrics["changeover_count"] == 3
    assert build_extra_cards(summary, metrics, {"invalid_due_count": 1})[0]["delta"] == 1
    assert build_freeze_display(summary)["state"] == "degraded"
    assert build_analysis_labels()["status"]["partial"] == "部分成功"


def test_analysis_viewmodel_split_preserves_legacy_compat_fallback() -> None:
    summary = {"algo": {"objective": "min_tardiness", "metrics": {"total_tardiness_hours": 3.5}}}

    ctx = build_analysis_context(
        selected_ver=8,
        raw_hist=[{"version": 8, "result_summary": summary}],
        selected_item={"version": 8, "result_summary": summary},
    )

    assert ctx["compat_fallback"]["used"] is True
    assert ctx["compat_fallback"]["missing_field_labels"] == ["优化对比指标", "系统比较顺序"]


def test_build_analysis_context_default_drops_diagnostics_injected_projector_redacts_algo() -> None:
    """① viewmodel 不依赖 service 层(架构 fitness),投影分两层保证:
    - 不注入 projector:默认兜底至少剔除 diagnostics(最敏感内部 trace 容器),不退回裸返回 raw;
    - 注入 service 的 project_public_result_summary(生产 route 走这条):algo 内部候选 key 也脱敏。
    """
    from core.services.scheduler.summary.optimizer_public_summary import project_public_result_summary

    summary = {
        "algo": {
            "objective": "min_overdue",
            "metrics": {"overdue_count": 1},
            "candidate_comparison": {"adopted_candidate_key": "graph_w1_of_3"},
        },
        "diagnostics": {"optimizer": {"attempts": [{"tag": "start:1"}]}},
    }
    raw_hist = [{"version": 11, "result_summary": summary}]
    selected_item = {"version": 11, "result_summary": summary}

    # 默认兜底:无注入 projector 也必须剔除 diagnostics,不裸返回 raw
    ctx_default = build_analysis_context(selected_ver=11, raw_hist=raw_hist, selected_item=selected_item)
    assert "diagnostics" not in ctx_default["selected_summary"]

    # 注入 service 单一真相源投影(生产路径):algo 内部候选 key 不外泄
    ctx_injected = build_analysis_context(
        selected_ver=11,
        raw_hist=raw_hist,
        selected_item=selected_item,
        public_summary_projector=project_public_result_summary,
    )
    injected_algo = ctx_injected["selected_summary"].get("algo") or {}
    assert "adopted_candidate_key" not in (injected_algo.get("candidate_comparison") or {})


def test_analysis_metric_cards_surface_non_finite_values_without_template_arithmetic() -> None:
    summary = _selected_summary()
    metrics = summary["algo"]["metrics"]
    metrics["overdue_count"] = "Infinity"
    metrics["machine_util_avg"] = "Infinity"
    metrics["machine_used_count"] = "NaN"
    metrics["machine_load_cv"] = "1e9999"

    ctx = build_analysis_context(
        selected_ver=9,
        raw_hist=[{"version": 9, "result_summary": summary}],
        selected_item={"version": 9, "result_summary": summary},
    )

    by_key = {card["key"]: card for card in ctx["metric_cards"]}
    assert by_key["overdue_count"]["value"] == "无法安全展示"
    assert by_key["machine_util_avg"]["value"] == "无法安全展示"
    assert "已用 无法安全展示 台" in by_key["machine_util_avg"]["secondary"]
    assert "任务分配均匀程度 无法安全展示，越小越均匀" in by_key["machine_util_avg"]["secondary"]
    json.dumps(ctx["metric_cards"], ensure_ascii=False, allow_nan=False)


def test_analysis_extra_cards_do_not_turn_unknown_values_into_zero() -> None:
    summary = _selected_summary()
    summary["invalid_due_count"] = ""
    summary["unscheduled_batch_count"] = "NaN"

    ctx = build_analysis_context(
        selected_ver=10,
        raw_hist=[{"version": 10, "result_summary": summary}],
        selected_item={"version": 10, "result_summary": summary},
    )

    by_key = {card["key"]: card for card in ctx["extra_cards"]}
    assert by_key["invalid_due_count"]["value"] == "无法安全展示"
    assert by_key["invalid_due_count"]["type_class"] == "type-danger"
    assert by_key["unscheduled_batch_count"]["value"] == "无法安全展示"
    assert by_key["unscheduled_batch_count"]["type_class"] == "type-danger"


def test_extra_cards_distinguish_missing_from_untrusted_values() -> None:
    cards = build_extra_cards(
        {
            "invalid_due_count": None,
            "unscheduled_batch_count": "   ",
        },
        None,
        None,
    )

    by_key = {card["key"]: card for card in cards}
    assert by_key["invalid_due_count"]["value"] == "无法安全展示"
    assert by_key["unscheduled_batch_count"]["value"] == "无法安全展示"
    assert by_key["invalid_due_count"]["type_class"] == "type-danger"
    assert by_key["unscheduled_batch_count"]["type_class"] == "type-danger"

    assert build_extra_cards({}, None, None) == []


def test_analysis_metric_cards_reject_boolean_values_as_untrusted_numbers() -> None:
    summary = _selected_summary()
    summary["invalid_due_count"] = False
    summary["unscheduled_batch_count"] = True
    metrics = summary["algo"]["metrics"]
    metrics["overdue_count"] = True
    metrics["machine_util_avg"] = False
    metrics["machine_used_count"] = True
    metrics["operator_util_avg"] = True
    metrics["operator_load_cv"] = False

    ctx = build_analysis_context(
        selected_ver=11,
        raw_hist=[{"version": 11, "result_summary": summary}],
        selected_item={"version": 11, "result_summary": summary},
    )

    extra_by_key = {card["key"]: card for card in ctx["extra_cards"]}
    assert extra_by_key["invalid_due_count"]["value"] == "无法安全展示"
    assert extra_by_key["unscheduled_batch_count"]["value"] == "无法安全展示"

    metric_by_key = {card["key"]: card for card in ctx["metric_cards"]}
    assert metric_by_key["overdue_count"]["value"] == "无法安全展示"
    assert metric_by_key["machine_util_avg"]["value"] == "无法安全展示"
    assert "已用 无法安全展示 台" in metric_by_key["machine_util_avg"]["secondary"]
    assert metric_by_key["operator_util_avg"]["value"] == "无法安全展示"
    assert "任务分配均匀程度 无法安全展示，越小越均匀" in metric_by_key["operator_util_avg"]["secondary"]
