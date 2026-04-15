from __future__ import annotations

from flask import Flask

import web.routes.normalizers as route_mod


def test_parse_result_summary_payload_accepts_dict_and_json_object(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.app_context():
        payload = {"algo": {"metrics": {"overdue_count": 1}}}
        assert route_mod._parse_result_summary_payload(payload, version=7, log_label="排产历史", source="history") == payload
        assert (
            route_mod._parse_result_summary_payload(
                '{"algo": {"metrics": {"overdue_count": 1}}}', version=7, log_label="排产历史", source="history"
            )
            == payload
        )

    assert warnings == []


def test_parse_result_summary_payload_rejects_non_dict_payloads_and_logs_warning(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.app_context():
        assert route_mod._parse_result_summary_payload("123", version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload("null", version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload('"text"', version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload("[]", version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload([], version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload(0, version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload(False, version=7, log_label="排产历史", source="history") is None

    assert len(warnings) == 7
    assert all("result_summary 结构不合法" in message for message in warnings)
    assert any("type=list" in message for message in warnings)
    assert any("type=int" in message for message in warnings)
    assert any("type=NoneType" in message for message in warnings)
    assert any("type=str" in message for message in warnings)
    assert any("type=bool" in message for message in warnings)



def test_parse_result_summary_payload_blank_string_short_circuits_but_whitespace_still_logs_parse_failure(monkeypatch) -> None:
    app = Flask(__name__)
    warnings = []

    def _fake_warning(message, *args, **kwargs):
        warnings.append(message % args if args else str(message))

    monkeypatch.setattr(app.logger, "warning", _fake_warning)

    with app.app_context():
        assert route_mod._parse_result_summary_payload("", version=7, log_label="排产历史", source="history") is None
        assert route_mod._parse_result_summary_payload("   ", version=7, log_label="排产历史", source="history") is None

    assert len(warnings) == 1
    assert "result_summary 解析失败" in warnings[0]
    assert "JSONDecodeError" in warnings[0]
