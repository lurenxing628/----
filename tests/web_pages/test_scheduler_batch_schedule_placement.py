"""批次详情排程去向卡视图模型（fusion-batch-detail-schedule-card）单测：
五态文案 + ok 态摘要 *_label/定位甘特链接 + 坏时间窗口缺失→链接 disabled +
history 缺失优雅降级 + op_rows 透传（纯函数，无 IO）。"""

from __future__ import annotations

from web.viewmodels.scheduler_batch_schedule_placement import build_schedule_placement

_OK_OP_ROWS = [
    {
        "op_label": "OP10",
        "plan_machine_label": "M1 设备1",
        "plan_operator_label": "O1 人员1",
        "execution_status_label": "已完工",
        "actual_start_time_label": "2026-06-01 08:05:00",
        "actual_end_time_label": "2026-06-01 16:30:00",
        "actual_summary_label": "现场状态：已完工；实际开工：2026-06-01 08:05:00；实际完工：2026-06-01 16:30:00",
        "has_execution_record": True,
    }
]


def test_non_ok_states_carry_honest_message_and_empty_fields() -> None:
    cases = {
        "no_official_plan": "尚无排产方案",
        "plan_empty": "最新方案暂无可用排程明细，请确认排产是否成功",
        "not_placed": "本批次未排入最新方案",
        "error": "排程信息读取失败，请到甘特图或排产历史确认。",
    }
    for state, message in cases.items():
        sp = build_schedule_placement(state=state)
        assert sp["state"] == state
        assert sp["message"] == message
        assert sp["op_rows"] == []
        assert sp["gantt_link"] is None
        assert sp["op_count"] == 0
        assert sp["version_label"] == "-"


def test_ok_state_builds_summary_labels_and_enabled_gantt_link() -> None:
    sp = build_schedule_placement(
        state="ok",
        batch_id="B001",
        version=8,
        op_count=1,
        op_rows=_OK_OP_ROWS,
        span_from_date="2026-06-01",
        span_to_date="2026-06-02",
        span_label="2026年6月1日 08:00 ～ 2026年6月2日 12:00",
        generated_at="2026-06-01 08:00:00",
        strategy="priority_first",
        history_present=True,
    )
    assert sp["state"] == "ok"
    assert sp["message"] == ""
    assert sp["version_label"] == "v8"
    assert sp["generated_at_label"] != "-"  # 喂了 generated_at，走 format_public_datetime
    assert sp["strategy_label"] != "-"
    assert sp["op_count"] == 1
    assert sp["span_label"] == "2026年6月1日 08:00 ～ 2026年6月2日 12:00"
    assert sp["op_rows"] == _OK_OP_ROWS
    # 版本 + 日期窗口齐全 → 定位甘特链接可用（非 disabled、有 url、带 gantt_batch）
    link = sp["gantt_link"]
    assert link is not None and link["disabled"] is False and link["url"]
    assert "gantt_batch=B001" in link["url"]
    assert "version=8" in link["url"]


def test_ok_state_bad_times_disable_gantt_link() -> None:
    # 行时间全坏 → 路由给 span_from_date/span_to_date=None → ctx 缺日期 → 链接 disabled
    sp = build_schedule_placement(
        state="ok",
        batch_id="B001",
        version=8,
        op_count=1,
        op_rows=_OK_OP_ROWS,
        span_from_date=None,
        span_to_date=None,
        span_label="时间记录异常",
        generated_at="2026-06-01 08:00:00",
        strategy="priority_first",
        history_present=True,
    )
    assert sp["span_label"] == "时间记录异常"
    assert sp["gantt_link"]["disabled"] is True


def test_ok_state_partial_span_surfaces_visible_notice() -> None:
    sp = build_schedule_placement(
        state="ok",
        batch_id="B001",
        version=8,
        op_count=3,
        op_rows=_OK_OP_ROWS,
        span_from_date="2026-06-01",
        span_to_date="2026-06-05",
        span_label="2026年6月1日 08:00 ～ 2026年6月5日 17:00",
        span_status="partial",
        span_bad_time_count=2,
        span_notice="有 2 条开始或结束时间写法不对，时间跨度只按可解析记录计算；已排工序数量仍是全量。",
        generated_at="2026-06-01 08:00:00",
        strategy="priority_first",
        history_present=True,
    )

    assert sp["op_count"] == 3
    assert sp["span_status"] == "partial"
    assert sp["span_bad_time_count"] == 2
    assert "时间跨度只按可解析记录计算" in sp["span_notice"]


def test_ok_state_history_absent_degrades_labels_not_crash() -> None:
    # hist 为 None（极端竞态）→ 不喂 generated_at/strategy → 走 4.2 缺失态「-」，摘要照常出
    sp = build_schedule_placement(
        state="ok",
        batch_id="B001",
        version=8,
        op_count=1,
        op_rows=_OK_OP_ROWS,
        span_from_date="2026-06-01",
        span_to_date="2026-06-02",
        span_label="2026年6月1日 08:00 ～ 2026年6月2日 12:00",
        generated_at=None,
        strategy=None,
        history_present=False,
    )
    assert sp["state"] == "ok"
    assert sp["version_label"] == "v8"
    assert sp["generated_at_label"] == "-"
    assert sp["strategy_label"] == "-"
