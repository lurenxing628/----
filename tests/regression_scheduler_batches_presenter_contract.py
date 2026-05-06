from __future__ import annotations

import pytest

from web.viewmodels import scheduler_batches_page as scheduler_batches_page_vm
from web.viewmodels.scheduler_batches_page import (
    _ALGO_MODE_LABELS,
    ScheduleHistoryDisplayValueError,
    build_degraded_latest_schedule_history_panel_state,
    build_latest_schedule_history_panel_state,
)


def _auto_assign_state(value):
    return {"label": "已启用" if value == "yes" else "-", "description": ""}


def test_latest_history_panel_builds_template_ready_items() -> None:
    panel = build_latest_schedule_history_panel_state(
        latest_history={
            "version": 8,
            "strategy": "priority_first",
            "result_status": "success",
            "schedule_time": "2026-05-05 10:00:00",
        },
        latest_summary={
            "algo": {
                "mode": "improve",
                "objective": "min_overdue",
                "metrics": {
                    "total_tardiness_hours": 2,
                    "weighted_tardiness_hours": 3,
                    "makespan_hours": 4,
                    "changeover_count": 1,
                    "machine_util_avg": 0.5,
                },
                "config_snapshot": {"auto_assign_persist": "yes"},
            },
            "overdue_batches": {"count": 2},
            "warnings": [],
            "errors": [],
        },
        latest_summary_parse_state={"parse_failed": False},
        auto_assign_persist_display_builder=_auto_assign_state,
    )

    assert panel.latest_strategy_label == "优先级优先"
    assert panel.latest_mode_label == _ALGO_MODE_LABELS["improve"]
    assert panel.latest_result_status_label == "成功"
    assert [item.label for item in panel.head_items] == ["版本", "结果", "排产时间"]
    assert [item.label for item in panel.meta_items] == ["排产方式", "模式", "目标"]
    assert [item.label for item in panel.metric_items] == [
        "超期数量",
        "拖期",
        "加权拖期",
        "总工期",
        "换型",
        "设备利用率",
    ]
    assert panel.metric_items[-1].value == "50.0%"
    assert panel.latest_auto_assign_persist_state["label"] == "已启用"
    assert panel.notice_items == ()
    assert panel.detail_notice_items == ()


def test_latest_history_panel_keeps_real_zero_metrics() -> None:
    panel = build_latest_schedule_history_panel_state(
        latest_history={
            "version": 8,
            "strategy": "priority_first",
            "result_status": "success",
            "schedule_time": "2026-05-05 10:00:00",
        },
        latest_summary={
            "algo": {
                "mode": "improve",
                "objective": "min_overdue",
                "metrics": {
                    "total_tardiness_hours": 0,
                    "weighted_tardiness_hours": 0,
                    "makespan_hours": 0,
                    "changeover_count": 0,
                    "machine_util_avg": 0,
                },
            },
            "overdue_batches": {"count": 0},
        },
        latest_summary_parse_state={"parse_failed": False},
        auto_assign_persist_display_builder=_auto_assign_state,
    )

    assert [item.value for item in panel.metric_items] == [
        "0 个",
        "0 小时",
        "0 小时",
        "0 小时",
        "0 次",
        "0.0%",
    ]


def test_latest_history_panel_rejects_unknown_strategy() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="未知排产策略：future_strategy"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "future_strategy",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary=None,
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_empty_strategy() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="排产历史缺少排产策略"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary=None,
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_unknown_algo_mode() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="未知排产模式：future_mode"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={"algo": {"mode": "future_mode", "objective": "min_overdue"}},
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_empty_algo_mode() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="排产历史摘要缺少排产模式"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={"algo": {"mode": "", "objective": "min_overdue"}},
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_missing_metric_key() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="metrics 缺少字段：weighted_tardiness_hours"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={
                "algo": {
                    "mode": "improve",
                    "objective": "min_overdue",
                    "metrics": {"total_tardiness_hours": 0},
                }
            },
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


@pytest.mark.parametrize("bad_value", (None, ""))
def test_latest_history_panel_rejects_empty_metric_value(bad_value) -> None:
    metrics = {
        "total_tardiness_hours": 0,
        "weighted_tardiness_hours": 0,
        "makespan_hours": 0,
        "changeover_count": 0,
        "machine_util_avg": 0,
    }
    metrics["makespan_hours"] = bad_value

    with pytest.raises(ScheduleHistoryDisplayValueError, match="metrics 字段为空：makespan_hours"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={
                "algo": {
                    "mode": "improve",
                    "objective": "min_overdue",
                    "metrics": metrics,
                }
            },
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


@pytest.mark.parametrize(
    ("metric_key", "bad_value"),
    (
        ("machine_util_avg", "abc"),
        ("machine_util_avg", {}),
        ("machine_util_avg", True),
        ("machine_util_avg", False),
        ("total_tardiness_hours", "N/A"),
        ("total_tardiness_hours", True),
        ("changeover_count", False),
        ("changeover_count", float("nan")),
    ),
)
def test_latest_history_panel_rejects_non_numeric_metric_value(metric_key: str, bad_value) -> None:
    metrics = {
        "total_tardiness_hours": 0,
        "weighted_tardiness_hours": 0,
        "makespan_hours": 0,
        "changeover_count": 0,
        "machine_util_avg": 0,
    }
    metrics[metric_key] = bad_value

    with pytest.raises(ScheduleHistoryDisplayValueError, match=f"metrics 字段不是数字：{metric_key}"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={
                "algo": {
                    "mode": "improve",
                    "objective": "min_overdue",
                    "metrics": metrics,
                }
            },
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_missing_overdue_count() -> None:
    with pytest.raises(ScheduleHistoryDisplayValueError, match="metrics 缺少字段：count"):
        build_latest_schedule_history_panel_state(
            latest_history={
                "version": 1,
                "strategy": "priority_first",
                "result_status": "success",
                "schedule_time": "2026-05-05 10:00:00",
            },
            latest_summary={
                "algo": {"mode": "improve", "objective": "min_overdue"},
                "overdue_batches": {},
            },
            latest_summary_parse_state={"parse_failed": False},
            auto_assign_persist_display_builder=_auto_assign_state,
        )


def test_latest_history_panel_rejects_non_numeric_overdue_count() -> None:
    for bad_value in ("N/A", True, False):
        with pytest.raises(ScheduleHistoryDisplayValueError, match="metrics 字段不是数字：count"):
            build_latest_schedule_history_panel_state(
                latest_history={
                    "version": 1,
                    "strategy": "priority_first",
                    "result_status": "success",
                    "schedule_time": "2026-05-05 10:00:00",
                },
                latest_summary={
                    "algo": {"mode": "improve", "objective": "min_overdue"},
                    "overdue_batches": {"count": bad_value},
                },
                latest_summary_parse_state={"parse_failed": False},
                auto_assign_persist_display_builder=_auto_assign_state,
            )


def test_degraded_latest_history_panel_keeps_secondary_degradation_messages(monkeypatch) -> None:
    secondary_messages = ({"code": "template_missing", "label": "组合合同模板资料不完整", "message": ""},)

    def _display_state(_summary, *, result_status, parse_state):
        return {
            "result_status_label": "成功",
            "display_secondary_degradation_messages": list(secondary_messages),
            "warnings_preview": [],
            "warning_total": 0,
            "warning_hidden_count": 0,
        }

    monkeypatch.setattr(scheduler_batches_page_vm, "build_summary_display_state", _display_state)

    panel = build_degraded_latest_schedule_history_panel_state(
        latest_history={
            "version": 1,
            "strategy": "priority_first",
            "result_status": "success",
            "schedule_time": "2026-05-05 10:00:00",
        },
        latest_summary={"algo": {}},
        latest_summary_parse_state={"parse_failed": False},
        error=ScheduleHistoryDisplayValueError("测试错误"),
    )

    assert list(panel.latest_other_degradation_messages) == list(secondary_messages)
    assert [notice.title for notice in panel.detail_notice_items] == ["其他需要注意的排产提示"]
    assert panel.detail_notice_items[0].detail_items == ("组合合同模板资料不完整",)


def test_latest_history_panel_builds_parse_and_warning_notices(monkeypatch) -> None:
    def _display_state(_summary, *, result_status, parse_state):
        return {
            "result_status_label": "成功",
            "summary_parse_state": {"parse_failed": True, "user_message": "摘要内容无法解析。"},
            "primary_degradation": {"message": "排产过程降级。", "details": ["缺少日历"]},
            "display_secondary_degradation_messages": [
                {"label": "组合合同资料不完整", "message": "已跳过组合并检查"}
            ],
            "warnings_preview": ["有 1 个批次交期较紧"],
            "warning_total": 2,
            "warning_hidden_count": 1,
        }

    monkeypatch.setattr(scheduler_batches_page_vm, "build_summary_display_state", _display_state)

    panel = build_latest_schedule_history_panel_state(
        latest_history={
            "version": 1,
            "strategy": "priority_first",
            "result_status": "success",
            "schedule_time": "2026-05-05 10:00:00",
        },
        latest_summary={"algo": {"mode": "improve", "objective": "min_overdue"}},
        latest_summary_parse_state={"parse_failed": True},
        auto_assign_persist_display_builder=_auto_assign_state,
    )

    assert [notice.title for notice in panel.notice_items] == ["排产历史摘要解析异常"]
    assert panel.notice_items[0].body == "摘要内容无法解析。"
    assert [notice.title for notice in panel.detail_notice_items] == [
        "排产过程需要注意",
        "其他需要注意的排产提示",
        "排产提醒",
    ]
    assert panel.detail_notice_items[0].detail_items == ("缺少日历",)
    assert panel.detail_notice_items[1].detail_items == ("组合合同资料不完整：已跳过组合并检查",)
    assert panel.detail_notice_items[2].footer == "另有 1 条提醒，请到系统历史查看。"
