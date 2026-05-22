from __future__ import annotations

from core.models.scheduler_history_parser import parse_result_summary_payload
from web.viewmodels.scheduler_history_summary import (
    build_history_summary_display,
    decorate_history_version_options,
    format_public_date,
    format_public_datetime,
    parse_history_summary_state,
    strategy_display_label,
)


def test_parse_result_summary_payload_accepts_dict_without_copying_contract() -> None:
    raw = {"completion_status": "success", "counts": {"scheduled_ops": 1}}
    result = parse_result_summary_payload(raw)

    assert result.payload == raw
    assert not result.parse_failed
    assert result.reason == "dict"


def test_parse_result_summary_payload_accepts_json_dict() -> None:
    result = parse_result_summary_payload('{"completion_status": "partial"}')

    assert result.payload == {"completion_status": "partial"}
    assert not result.parse_failed
    assert result.reason == "json"


def test_parse_result_summary_payload_reports_json_decode_error() -> None:
    result = parse_result_summary_payload("{bad json")

    assert result.payload is None
    assert result.parse_failed
    assert result.reason == "json_decode_error"


def test_parse_result_summary_payload_rejects_json_list_as_invalid_structure() -> None:
    result = parse_result_summary_payload('["not", "dict"]')

    assert result.payload is None
    assert result.parse_failed
    assert result.reason == "invalid_structure"


def test_parse_history_summary_state_keeps_existing_user_message_for_parse_failure() -> None:
    state = parse_history_summary_state("{bad json")

    assert state["parse_failed"] is True
    assert state["reason"] == "json_decode_error"
    assert state["user_message"] == "当前版本的排产摘要读取失败，页面仅展示基础历史信息。"


def test_decorate_history_version_options_preserves_status_label_contract() -> None:
    rows = [
        {
            "version": 3,
            "result_status": "success",
            "result_summary": '{"completion_status": "partial"}',
        }
    ]

    decorated = decorate_history_version_options(rows)

    assert decorated[0]["version"] == 3
    assert decorated[0]["result_status_label"] == "部分成功"
    assert decorated[0]["strategy_display_state"] == "missing"
    assert decorated[0]["strategy_label"] == "旧历史未记录"
    assert "旧版本" in decorated[0]["strategy_display_message"]


def test_history_time_display_uses_chinese_business_format() -> None:
    assert format_public_date("2026-05-04") == "2026年5月4日"
    assert format_public_datetime("2026-05-04 03:20:59") == "2026年5月4日 03:20"
    assert format_public_datetime("Wed, 13 May 2026 00:00:00 GMT") == "2026年5月13日 00:00"

    decorated = decorate_history_version_options(
        [{"version": 4, "schedule_time": "2026-05-05 10:00:00", "result_status": "ok", "result_summary": "{}"}]
    )

    assert decorated[0]["schedule_time_display"] == "2026年5月5日 10:00"


def test_decorate_history_version_options_keeps_legacy_status_aliases() -> None:
    decorated = decorate_history_version_options(
        [
            {"version": 4, "strategy": "priority_first", "result_status": "ok", "result_summary": "{}"},
            {"version": 5, "strategy": "priority_first", "result_status": "ok2", "result_summary": "{}"},
            {"version": 6, "strategy": "priority_first", "result_status": "fail", "result_summary": "{}"},
        ]
    )

    assert decorated[0]["result_status_label"] == "成功"
    assert decorated[0]["version_option_label"] == "v4 · 成功"
    assert decorated[1]["result_status_label"] == "成功"
    assert decorated[1]["version_option_label"] == "v5 · 成功"
    assert decorated[2]["result_status_label"] == "失败"
    assert decorated[2]["version_option_label"] == "v6 · 失败"


def test_strategy_display_label_marks_unknown_values_as_history_error() -> None:
    assert strategy_display_label("priority_first") == "优先级优先"
    assert strategy_display_label("") == "旧历史未记录"
    assert strategy_display_label("future_strategy") == "历史记录异常"

    decorated = decorate_history_version_options(
        [
            {
                "version": 4,
                "strategy": "future_strategy",
                "result_status": "success",
                "result_summary": '{"completion_status": "success"}',
            }
        ]
    )
    row = decorated[0]
    assert row["strategy_display_state"] == "invalid"
    assert row["strategy_label"] == "历史记录异常"
    assert "future_strategy" in row["strategy_display_message"]


def test_build_history_summary_display_keeps_parse_state_visible() -> None:
    display = build_history_summary_display(
        raw_summary="{bad json",
        result_status="success",
    )

    assert display["summary_parse_state"]["parse_failed"] is True
    assert display["summary_parse_state"]["reason"] == "json_decode_error"
