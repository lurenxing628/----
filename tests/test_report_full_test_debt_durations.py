"""单元测试：tools/report_full_test_debt_durations.build_duration_report——按 nodeid 聚合 call 耗时 Top-N、按文件聚合 setup/call/teardown 总耗时并按类别小计的报表口径。"""

from __future__ import annotations

from tools.report_full_test_debt_durations import build_duration_report


def test_duration_report_groups_call_file_and_category_totals() -> None:
    payload = {
        "summary": {"collected_count": 3},
        "reports": [
            {
                "nodeid": "tests/regression_ui_browser_geometry_smoke.py::test_browser",
                "when": "setup",
                "duration": 0.5,
            },
            {
                "nodeid": "tests/regression_ui_browser_geometry_smoke.py::test_browser",
                "when": "call",
                "duration": 9.0,
            },
            {
                "nodeid": "tests/test_scheduler_batches_page_viewmodel.py::test_page",
                "when": "call",
                "duration": 2.0,
            },
            {
                "nodeid": "tests/test_architecture_fitness.py::test_arch",
                "when": "call",
                "duration": 3.0,
            },
        ],
    }

    report = build_duration_report(payload, top_nodeids=2, top_files=3)
    call_section = report.split("Top 2 call nodeids", 1)[1].split(
        "Top 3 files by setup/call/teardown duration",
        1,
    )[0]

    assert "reports: 4" in report
    assert "tests/regression_ui_browser_geometry_smoke.py::test_browser" in call_section
    assert "tests/test_architecture_fitness.py::test_arch" in call_section
    assert "tests/test_scheduler_batches_page_viewmodel.py::test_page" not in call_section
    assert "tests/test_architecture_fitness.py" in report
    assert "tests/test_scheduler_batches_page_viewmodel.py" in report
    assert "9.500s  tests/regression_ui_browser_geometry_smoke.py" in report
    assert "9.000s  tests/regression_ui_browser_geometry_smoke.py" in report
    assert "9.500s  browser" in report
    assert "browser" in report
    assert "scheduler_batches" in report
    assert "architecture" in report
