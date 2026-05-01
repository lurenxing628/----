from __future__ import annotations

from pathlib import Path


def test_result_summary_json_parsing_lives_in_core_parser() -> None:
    route_normalizers = Path("web/routes/normalizers.py").read_text(encoding="utf-8")
    trend_viewmodel = Path("web/viewmodels/scheduler_analysis_trends.py").read_text(encoding="utf-8")

    assert "json.loads" not in route_normalizers
    assert "json.loads" not in trend_viewmodel
    assert "parse_result_summary_payload" in route_normalizers
    assert "parse_result_summary_payload" in trend_viewmodel


def test_history_summary_parser_does_not_swallow_unknown_exceptions() -> None:
    parser_source = Path("core/models/scheduler_history_parser.py").read_text(
        encoding="utf-8"
    )
    service_facade_source = Path("core/services/scheduler/history_summary_parser.py").read_text(encoding="utf-8")

    assert "except Exception" not in parser_source
    assert "JSONDecodeError" in parser_source
    assert "parse_result_summary_payload" in service_facade_source


def test_result_summary_pages_use_history_summary_viewmodel() -> None:
    page_paths = [
        "web/routes/domains/scheduler/scheduler_analysis.py",
        "web/routes/domains/scheduler/scheduler_batches.py",
        "web/routes/domains/scheduler/scheduler_week_plan.py",
        "web/routes/system_history.py",
    ]
    for page_path in page_paths:
        source = Path(page_path).read_text(encoding="utf-8")

        assert "_parse_result_summary_payload_with_meta" not in source
        assert "parse_history_summary_state" in source
