from __future__ import annotations

from flask import Flask

from web.routes.history_summary_logging import (
    log_history_summary_parse_warning,
    log_history_version_option_parse_warnings,
)
from web.viewmodels.scheduler_history_summary import parse_history_summary_state


def _capture_warnings(app: Flask, monkeypatch):
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)
    return warnings


def test_history_summary_viewmodel_accepts_dict_and_json_object(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = _capture_warnings(app, monkeypatch)

    with app.app_context():
        payload = {"algo": {"metrics": {"overdue_count": 1}}}
        dict_state = parse_history_summary_state(payload)
        json_state = parse_history_summary_state('{"algo": {"metrics": {"overdue_count": 1}}}')

        log_history_summary_parse_warning(dict_state, version=7, log_label="排产历史", source="history")
        log_history_summary_parse_warning(json_state, version=7, log_label="排产历史", source="history")

    assert dict_state["payload"] == payload
    assert dict_state["reason"] == "dict"
    assert dict_state["parse_failed"] is False
    assert json_state["payload"] == payload
    assert json_state["reason"] == "json"
    assert json_state["parse_failed"] is False
    assert warnings == []


def test_history_summary_logging_reports_non_dict_payloads(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = _capture_warnings(app, monkeypatch)

    with app.app_context():
        for raw in ("123", "null", '"text"', "[]", [], 0, False):
            state = parse_history_summary_state(raw)
            assert state["payload"] is None
            assert state["parse_failed"] is True
            assert state["reason"] == "invalid_structure"
            log_history_summary_parse_warning(state, version=7, log_label="排产历史", source="history")

    assert len(warnings) == 7
    assert all("result_summary 结构不合法" in message for message in warnings)
    assert any("type=list" in message for message in warnings)
    assert any("type=int" in message for message in warnings)
    assert any("type=NoneType" in message for message in warnings)
    assert any("type=str" in message for message in warnings)
    assert any("type=bool" in message for message in warnings)


def test_history_summary_logging_keeps_missing_quiet_but_reports_bad_whitespace(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = _capture_warnings(app, monkeypatch)

    with app.app_context():
        missing_state = parse_history_summary_state("")
        bad_json_state = parse_history_summary_state("   ")

        assert missing_state["payload"] is None
        assert missing_state["parse_failed"] is False
        assert missing_state["reason"] == "missing"
        log_history_summary_parse_warning(missing_state, version=7, log_label="排产历史", source="history")

        assert bad_json_state["payload"] is None
        assert bad_json_state["parse_failed"] is True
        assert bad_json_state["reason"] == "json_decode_error"
        log_history_summary_parse_warning(bad_json_state, version=7, log_label="排产历史", source="history")

    assert len(warnings) == 1
    assert "result_summary 解析失败" in warnings[0]
    assert "JSONDecodeError" in warnings[0]


def test_history_version_option_logging_reports_bad_summary(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = _capture_warnings(app, monkeypatch)

    with app.app_context():
        log_history_version_option_parse_warnings(
            [
                {"version": 8, "result_summary": "{bad json"},
                {"version": 9, "result_summary": ""},
            ],
            log_label="排产历史",
        )

    assert len(warnings) == 1
    assert "排产历史 result_summary 解析失败（version=8, source=version_option" in warnings[0]
    assert "JSONDecodeError" in warnings[0]
