from __future__ import annotations

from core.models.scheduler_history_parser import parse_result_summary_payload
from web.viewmodels.scheduler_history_summary import (
    build_history_summary_display,
    decorate_history_version_options,
    parse_history_summary_state,
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
    assert state["user_message"] == "当前版本的排产摘要解析失败，页面仅展示基础历史信息。"


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


def test_build_history_summary_display_keeps_parse_state_visible() -> None:
    display = build_history_summary_display(
        raw_summary="{bad json",
        result_status="success",
    )

    assert display["summary_parse_state"]["parse_failed"] is True
    assert display["summary_parse_state"]["reason"] == "json_decode_error"
