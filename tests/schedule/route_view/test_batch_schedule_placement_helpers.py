"""排程去向卡路由层纯 helper 单测（_placement_op_row / _placement_span）。

这两个 helper 是路由内的纯函数（不碰 g/request），把计划行 + 4.10 facts 字典装配成
只含公开 label 的工序行、把行时间解析成甘特链接日期窗口。直接 import 单测，钉死：
- facts 以 int(op_id) 为键，op_id 走字符串也经 int 强转命中（防类型漂移静默 miss）；
- 缺事实工序走「暂未记录现场实际」诚实态、非崩；
- 外协行计划设备/人员走 display_* 兜底文案不空白；
- op_rows 仅 8 个公开 label 键、无 op_id/machine_id 等 raw 内部身份外显；
- span 解析跳坏值、start/end 各独立 min/max，全坏→「时间记录异常」+ 无日期窗口。
"""

from __future__ import annotations

from types import SimpleNamespace

from core.models.operation_execution_event import EXECUTION_STATUS_COMPLETED
from web.routes.domains.scheduler.scheduler_batch_detail import (
    _placement_op_row,
    _placement_span,
)

_PUBLIC_OP_ROW_KEYS = {
    "op_label",
    "plan_machine_label",
    "plan_operator_label",
    "execution_status_label",
    "actual_start_time_label",
    "actual_end_time_label",
    "actual_summary_label",
    "has_execution_record",
}

_INTERNAL_ROW = {
    "op_id": 1,
    "op_code": "OP10",
    "machine_id": "M1",
    "machine_name": "设备1",
    "operator_id": "O1",
    "operator_name": "人员1",
    # raw 内部身份故意塞进来，验证 helper 不会把它们外显到 op_row
    "schedule_id": 100,
    "scenario_id": "SC1",
    "source_table": "schedule",
    "candidate_id": 7,
}


def _completed_fact() -> SimpleNamespace:
    return SimpleNamespace(
        actual_status=EXECUTION_STATUS_COMPLETED,
        actual_start_time="2026-06-01 08:05:00",
        actual_end_time="2026-06-01 16:30:00",
    )


def test_op_row_facts_hit_int_key() -> None:
    row = _placement_op_row(dict(_INTERNAL_ROW), {1: _completed_fact()})
    assert row["op_label"] == "OP10"
    assert row["plan_machine_label"] == "M1 设备1"
    assert row["plan_operator_label"] == "O1 人员1"
    assert row["has_execution_record"] is True
    assert row["actual_start_time_label"] == "2026-06-01 08:05:00"
    assert row["actual_end_time_label"] == "2026-06-01 16:30:00"
    # 仅 8 个公开 label 键，无 op_id/schedule_id/scenario_id/source_table/candidate_id 等 raw 内部身份
    assert set(row.keys()) == _PUBLIC_OP_ROW_KEYS


def test_op_row_facts_miss_is_honest_not_recorded() -> None:
    row = _placement_op_row(dict(_INTERNAL_ROW), {})
    assert row["has_execution_record"] is False
    assert row["actual_summary_label"] == "暂未记录现场实际"
    assert set(row.keys()) == _PUBLIC_OP_ROW_KEYS


def test_op_row_string_op_id_still_hits_via_int_coercion() -> None:
    # op_id 走字符串路径时仍经 int 强转命中 int 键事实——防未来类型漂移退化成静默 miss
    str_id_row = dict(_INTERNAL_ROW, op_id="1")
    row = _placement_op_row(str_id_row, {1: _completed_fact()})
    assert row["has_execution_record"] is True
    assert row["execution_status_label"]


def test_op_row_external_uses_display_fallback_labels() -> None:
    external_row = {
        "op_id": 2,
        "op_code": "OP20",
        "machine_id": None,
        "machine_name": None,
        "supplier_name": "供应商X",
        "operator_id": None,
        "operator_name": None,
    }
    row = _placement_op_row(external_row, {})
    assert row["plan_machine_label"] == "外协 供应商X"
    assert row["plan_operator_label"] == "外协/未分配"


def test_span_all_valid_independent_min_max() -> None:
    rows = [
        {"start_time": "2026-06-02 09:00:00", "end_time": "2026-06-02 11:00:00"},
        {"start_time": "2026-06-01 08:00:00", "end_time": "2026-06-03 17:00:00"},
        {"start_time": "2026-06-01 14:00:00", "end_time": "2026-06-02 18:00:00"},
    ]
    from_date, to_date, label = _placement_span(rows)
    assert from_date == "2026-06-01"
    assert to_date == "2026-06-03"
    assert "～" in label


def test_span_mixed_skips_bad_time_rows() -> None:
    rows = [
        {"start_time": "2026-06-01 08:00:00", "end_time": "坏值"},
        {"start_time": "坏值", "end_time": "2026-06-05 17:00:00"},
        {"start_time": "2026-06-02 09:00:00", "end_time": "2026-06-03 12:00:00"},
    ]
    from_date, to_date, label = _placement_span(rows)
    # start 可解析的最早是 06-01，end 可解析的最晚是 06-05
    assert from_date == "2026-06-01"
    assert to_date == "2026-06-05"
    assert "～" in label


def test_span_all_bad_returns_no_window() -> None:
    rows = [
        {"start_time": "坏值", "end_time": None},
        {"start_time": None, "end_time": "也坏"},
    ]
    assert _placement_span(rows) == (None, None, "时间记录异常")


def test_span_empty_rows_returns_no_window() -> None:
    assert _placement_span([]) == (None, None, "时间记录异常")
