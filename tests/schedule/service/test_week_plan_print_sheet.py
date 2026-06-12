"""周派工单重分组单测（fusion-dispatch-print-sheet）。

钉死点：双视图分组与兜底段固定最后；machine 视图全部外协行归兜底段
（重名供应商不按串各自成段——错并组消解）；行恰七键 drop「现场状态」
（4.11 纸面零现场事实）；day 等值过滤后空组不出现；group_by 非法 raise。
"""

from __future__ import annotations

import pytest

from core.services.scheduler.week_plan_print_sheet import (
    FALLBACK_RESOURCE_LABEL,
    build_week_plan_print_sheets,
)

_PRINT_KEYS = {"日期", "批次号", "图号", "工序", "设备", "人员", "时段"}


def _row(date="2026-06-01", batch="B1", machine="M1 车床", operator="OP1 张三", slot="08:00-12:00"):
    return {
        "日期": date,
        "批次号": batch,
        "图号": "P1",
        "工序": 10,
        "设备": machine,
        "人员": operator,
        "时段": slot,
        "现场状态": "生产中",
    }


def test_machine_view_groups_by_machine_label_and_sorts():
    sheets = build_week_plan_print_sheets(
        [_row(machine="M2 铣床"), _row(machine="M1 车床", batch="B2"), _row(machine="M2 铣床", batch="B3")],
        group_by="machine",
    )
    assert [s["resource_label"] for s in sheets] == ["M1 车床", "M2 铣床"]
    assert len(sheets[1]["rows"]) == 2


def test_machine_view_outsourced_rows_merge_into_fallback_last():
    # 两个重名供应商串 + 无设备行：统一归兜底段（不按供应商串各自成段），
    # 行内「设备」列保留各自串做参照
    sheets = build_week_plan_print_sheets(
        [
            _row(machine="外协 华东外协"),
            _row(machine="外协 华东外协", batch="B2"),
            _row(machine="外协/未分配", batch="B3"),
            _row(machine="M1 车床", batch="B4"),
        ],
        group_by="machine",
    )
    assert [s["resource_label"] for s in sheets] == ["M1 车床", FALLBACK_RESOURCE_LABEL]
    fallback_rows = sheets[1]["rows"]
    assert len(fallback_rows) == 3
    assert {r["设备"] for r in fallback_rows} == {"外协 华东外协", "外协/未分配"}


def test_operator_view_unassigned_fallback_last():
    sheets = build_week_plan_print_sheets(
        [_row(operator="外协/未分配"), _row(operator="OP1 张三", batch="B2"), _row(operator="OP2 李四", batch="B3")],
        group_by="operator",
    )
    assert [s["resource_label"] for s in sheets] == ["OP1 张三", "OP2 李四", FALLBACK_RESOURCE_LABEL]


def test_print_rows_have_exactly_seven_keys_no_execution_status():
    sheets = build_week_plan_print_sheets([_row()], group_by="machine")
    assert set(sheets[0]["rows"][0].keys()) == _PRINT_KEYS  # 4.11：现场状态不进纸


def test_day_filter_keeps_only_that_day_and_drops_empty_groups():
    sheets = build_week_plan_print_sheets(
        [
            _row(date="2026-06-01", machine="M1 车床"),
            _row(date="2026-06-02", machine="M2 铣床", batch="B2"),
        ],
        group_by="machine",
        day="2026-06-02",
    )
    assert [s["resource_label"] for s in sheets] == ["M2 铣床"]
    assert sheets[0]["rows"][0]["日期"] == "2026-06-02"


def test_sheet_rows_resorted_by_date_then_slot():
    # 上游排序键无时段（日期→设备→人员→批次→工序）：同段同日不同时段的行
    # 重分组后必须按时间重排；「全天」归一排当日最前
    sheets = build_week_plan_print_sheets(
        [
            _row(slot="13:00-17:00", operator="OP2 李四", batch="B2"),
            _row(slot="08:00-12:00", operator="OP9 王五", batch="B1"),
            _row(date="2026-06-02", slot="全天", batch="B4"),
            _row(date="2026-06-02", slot="06:00-08:00", batch="B3"),
        ],
        group_by="machine",
    )
    assert [r["批次号"] for r in sheets[0]["rows"]] == ["B1", "B2", "B4", "B3"]


def test_empty_rows_returns_empty_list():
    assert build_week_plan_print_sheets([], group_by="operator") == []


def test_unknown_group_by_raises():
    with pytest.raises(ValueError, match="machine / operator"):
        build_week_plan_print_sheets([_row()], group_by="bogus")
