from __future__ import annotations

import pytest

from web.viewmodels.scheduler_batches_page import (
    _ALGO_MODE_LABELS,
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


def test_latest_history_panel_rejects_unknown_strategy() -> None:
    with pytest.raises(KeyError):
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


def test_latest_history_panel_rejects_unknown_algo_mode() -> None:
    with pytest.raises(KeyError):
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
