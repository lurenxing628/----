"""周计划增强单测（fusion-week-plan-enrich）：现场状态注入 + 每日合计。

钉死点：facts=None 显示「-」与提供后无 fact「待开工」两态区分；同工序跨日
段行同状态；段行恰好八个中文键零内部键；minutes_by_date 旁路与公开 rows
物理分离；容量正午采样（跨午夜班次正午≠午夜采样结果，4.6 反例）；
休息日容量 0 →「利用率暂时算不了」诚实降级。
"""

from __future__ import annotations

from datetime import datetime, time
from types import SimpleNamespace

from core.services.scheduler.gantt_range import resolve_week_range
from core.services.scheduler.gantt_week_plan import build_week_plan_rows
from core.services.scheduler.week_plan_daily_summary import (
    LOAD_UNAVAILABLE_LABEL,
    build_week_plan_daily_summary,
)

_WR = resolve_week_range(week_start="2026-06-01")

_EXPECTED_KEYS = {"日期", "批次号", "图号", "工序", "设备", "人员", "时段", "现场状态"}


def _row(op_id=1, start="2026-06-01 08:00:00", end="2026-06-01 12:00:00", batch="B1"):
    return {
        "op_id": op_id,
        "batch_id": batch,
        "part_no": "P1",
        "seq": 10,
        "machine_id": "M1",
        "machine_name": "车床",
        "operator_id": "OP1",
        "operator_name": "张三",
        "start_time": start,
        "end_time": end,
    }


def _fact(status):
    return SimpleNamespace(actual_status=status)


# ---------- 现场状态注入 ----------


def test_facts_none_renders_dash():
    outcome, _minutes = build_week_plan_rows(rows=[_row()], wr=_WR)
    assert outcome.value[0]["现场状态"] == "-"


def test_fact_status_label_and_no_fact_not_started():
    outcome, _minutes = build_week_plan_rows(
        rows=[_row(op_id=1), _row(op_id=2, batch="B2")],
        wr=_WR,
        execution_facts_by_op_id={1: _fact("processing")},
    )
    by_batch = {r["批次号"]: r for r in outcome.value}
    assert by_batch["B1"]["现场状态"] == "生产中"
    # 提供了 facts 但该工序无 fact：计划行没有事实=尚未开工，不是数据缺口
    assert by_batch["B2"]["现场状态"] == "待开工"


def test_cross_day_segments_share_same_status():
    outcome, _minutes = build_week_plan_rows(
        rows=[_row(op_id=1, start="2026-06-01 20:00:00", end="2026-06-02 04:00:00")],
        wr=_WR,
        execution_facts_by_op_id={1: _fact("completed")},
    )
    assert len(outcome.value) == 2  # 跨日拆两段
    assert {r["现场状态"] for r in outcome.value} == {"已完工"}


def test_segment_rows_have_exactly_eight_public_keys():
    outcome, _minutes = build_week_plan_rows(rows=[_row()], wr=_WR)
    assert set(outcome.value[0].keys()) == _EXPECTED_KEYS  # 零内部键（4.6）


# ---------- minutes_by_date 旁路 ----------


def test_minutes_by_date_accumulates_per_day():
    outcome, minutes = build_week_plan_rows(
        rows=[
            _row(op_id=1, start="2026-06-01 08:00:00", end="2026-06-01 12:00:00"),
            _row(op_id=2, start="2026-06-01 13:00:00", end="2026-06-01 16:00:00", batch="B2"),
            _row(op_id=3, start="2026-06-01 22:00:00", end="2026-06-02 02:00:00", batch="B3"),
        ],
        wr=_WR,
    )
    # 6-01：4h+3h+2h（跨午夜段只算当日 22:00-24:00）=540min；6-02：2h=120min
    assert minutes == {"2026-06-01": 540, "2026-06-02": 120}
    assert len(outcome.value) == 4


# ---------- 每日合计（4.6 容量口径） ----------


class _CalendarStub:
    """policy_for_datetime 最小桩：按 (date, hour) 返回 policy，记录采样时刻。"""

    def __init__(self, policies):
        self._policies = policies
        self.sampled = []

    def policy_for_datetime(self, dt):
        self.sampled.append(dt)
        return self._policies[dt.date().isoformat()]


def _policy(shift_hours, efficiency=1.0):
    return SimpleNamespace(shift_hours=shift_hours, efficiency=efficiency)


def test_daily_summary_noon_sampling_and_load():
    cal = _CalendarStub({"2026-06-01": _policy(8, 0.9)})
    out = build_week_plan_daily_summary(
        {"2026-06-01": 540}, calendar=cal, week_start=None, week_end=None
    )
    assert out == [
        {
            "date": "2026-06-01",
            "planned_hours_label": "9 小时",
            "capacity_hours_label": "7.2 小时",
            "load_label": "125%",
        }
    ]
    # 4.6 钉死：采样时刻必须是正午（midnight 采样在跨午夜班次归属错日）
    assert cal.sampled == [datetime(2026, 6, 1, 12, 0)]
    assert cal.sampled[0].time() == time(12, 0)


def test_daily_summary_rest_day_capacity_zero_honest_label():
    cal = _CalendarStub({"2026-06-01": _policy(0)})
    out = build_week_plan_daily_summary(
        {"2026-06-01": 120}, calendar=cal, week_start=None, week_end=None
    )
    assert out[0]["capacity_hours_label"] == "0 小时"
    assert out[0]["load_label"] == LOAD_UNAVAILABLE_LABEL


def test_daily_summary_policy_failure_degrades_honestly():
    class _Boom:
        def policy_for_datetime(self, dt):
            raise ValueError("calendar broken")

    out = build_week_plan_daily_summary(
        {"2026-06-01": 60}, calendar=_Boom(), week_start=None, week_end=None
    )
    assert out[0]["capacity_hours_label"] == "-"
    assert out[0]["load_label"] == LOAD_UNAVAILABLE_LABEL


def test_daily_summary_empty_input_returns_empty():
    assert build_week_plan_daily_summary({}, calendar=_CalendarStub({}), week_start=None, week_end=None) == []
