"""execution_detail_meta 单源行为锚（fusion-batch-detail-schedule-card 从
gantt_tasks 抽取并去前缀公开，只搬不改）：无事实诚实文案 + ISO 时间标签 + 键集恰为
公开 *_label/has_execution_record 加两个甘特旧合同保留的裸 actual_*_time（_PUBLIC_KEYS
钉死这 7 键）。防未来改动这条 4.10 现场标签单源时静默漂移。"""

from __future__ import annotations

from types import SimpleNamespace

from core.models.operation_execution_event import (
    EXECUTION_STATUS_COMPLETED,
    EXECUTION_STATUS_PROCESSING,
)
from core.services.scheduler.execution_fact_presentation import execution_detail_meta

_PUBLIC_KEYS = {
    "execution_status_label",
    "actual_start_time",
    "actual_end_time",
    "actual_start_time_label",
    "actual_end_time_label",
    "actual_summary_label",
    "has_execution_record",
}


def test_no_fact_is_honest_not_recorded() -> None:
    meta = execution_detail_meta(None)
    assert meta["has_execution_record"] is False
    assert meta["actual_summary_label"] == "暂未记录现场实际"
    assert meta["actual_start_time_label"] == "暂无实际开工"
    assert meta["actual_end_time_label"] == "暂无实际完工"
    assert set(meta.keys()) == _PUBLIC_KEYS


def test_completed_fact_uses_iso_time_labels() -> None:
    fact = SimpleNamespace(
        actual_status=EXECUTION_STATUS_COMPLETED,
        actual_start_time="2026-06-01 08:05:00",
        actual_end_time="2026-06-01 16:30:00",
    )
    meta = execution_detail_meta(fact)
    assert meta["has_execution_record"] is True
    # ISO 形态 YYYY-MM-DD HH:MM:SS（经 _sched_display_utils.fmt_dt），非中文
    assert meta["actual_start_time_label"] == "2026-06-01 08:05:00"
    assert meta["actual_end_time_label"] == "2026-06-01 16:30:00"
    assert "现场状态" in meta["actual_summary_label"]


def test_processing_without_times_still_has_record() -> None:
    fact = SimpleNamespace(actual_status=EXECUTION_STATUS_PROCESSING, actual_start_time=None, actual_end_time=None)
    meta = execution_detail_meta(fact)
    assert meta["has_execution_record"] is True
    assert meta["actual_start_time_label"] == "暂无实际开工"
    assert meta["actual_end_time_label"] == "暂无实际完工"
