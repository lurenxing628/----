from __future__ import annotations

from pathlib import Path


def test_result_summary_json_parsing_lives_in_core_parser() -> None:
    route_normalizers = Path("web/routes/normalizers.py").read_text(encoding="utf-8")
    trend_viewmodel = Path("web/viewmodels/scheduler_analysis_trends.py").read_text(encoding="utf-8")

    assert "json.loads" not in route_normalizers
    assert "json.loads" not in trend_viewmodel
    assert "parse_result_summary_payload" not in route_normalizers
    assert "parse_result_summary_payload" in trend_viewmodel
    assert "_parse_result_summary_payload_with_meta" not in route_normalizers
    assert "_parse_result_summary_payload" not in route_normalizers
    assert "_log_result_summary_warning" not in route_normalizers
    assert "decorate_history_version_options" not in route_normalizers


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
        "web/routes/dashboard.py",
        "web/routes/domains/scheduler/scheduler_analysis.py",
        "web/routes/domains/scheduler/scheduler_batches.py",
        "web/routes/domains/scheduler/scheduler_week_plan.py",
        "web/routes/system_history.py",
        "web/routes/reports.py",
        "web/routes/domains/scheduler/scheduler_resource_dispatch.py",
        "web/routes/domains/scheduler/scheduler_gantt.py",
    ]
    for page_path in page_paths:
        source = Path(page_path).read_text(encoding="utf-8")

        assert "_parse_result_summary_payload_with_meta" not in source
        assert "_parse_result_summary_payload" not in source
        assert "from web.routes.normalizers import decorate_history_version_options" not in source


def test_pages_do_not_import_result_summary_helpers_from_route_normalizers() -> None:
    for page_path in Path("web/routes").rglob("*.py"):
        source = page_path.read_text(encoding="utf-8")

        assert "from .normalizers import _parse_result_summary_payload" not in source
        assert "from web.routes.normalizers import _parse_result_summary_payload" not in source
        assert "from .normalizers import decorate_history_version_options" not in source
        assert "from web.routes.normalizers import decorate_history_version_options" not in source
