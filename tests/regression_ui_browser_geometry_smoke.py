from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, cast

from tests.ui_geometry_browser_support import (
    EXPECTED_PAGE_SIGNALS,
    SMOKE_PATHS,
    _build_app,
    _find_chrome,
    _find_node_with_browser_runtime,
    _run_chrome_geometry_probe,
    _serve_app,
    _shutdown_served_app,
)


def test_ui_pages_do_not_create_body_level_overflow_in_real_browser(tmp_path, monkeypatch) -> None:
    chrome = _find_chrome()
    node = _find_node_with_browser_runtime()
    app = _build_app(tmp_path, monkeypatch)
    served = _serve_app(app)
    try:
        results = _run_chrome_geometry_probe(
            chrome_path=chrome.chrome_path,
            node_path=node.node_path,
            base_url=served.base_url,
            tmp_path=tmp_path,
            chrome_info=chrome,
            node_info=node,
        )
    finally:
        _shutdown_served_app(served)

    overflowing = [item for item in results if item["bodyOverflow"]]
    overlapping_toggles = [item for item in results if item["toggleOverlapCount"]]
    bad_dark_summary = [item for item in results if item["darkSummaryBadCount"]]
    bad_dark_summary_contrast = [item for item in results if item["darkLowContrastSummaryCount"]]
    bad_dark_text_contrast = [item for item in results if item["darkLowContrastTextCount"]]
    bad_dark_notice = [item for item in results if item["darkNoticeBadCount"]]
    bad_logs_table = [item for item in results if not item["logsTableMultiline"]]
    bad_multiline_tables = [
        item
        for item in results
        if any(not ok for ok in dict(item["multilineTableChecks"]).values())
    ]
    missing_required_toggles = [item for item in results if item["missingRequiredToggleIds"]]
    bad_http_status = [item for item in results if item["httpStatus"] != 200]
    bad_shell = [item for item in results if not item["hasAppShell"]]
    error_pages = [item for item in results if item["pageLooksError"]]
    wrong_paths = [item for item in results if item["pathMismatch"]]
    missing_expected_texts = [item for item in results if item["missingExpectedTexts"]]
    missing_expected_ids = [item for item in results if item["missingExpectedIds"]]

    failures: List[Dict[str, Any]] = []

    def add_failure(kind: str, rows: List[Dict[str, Any]], detail_keys: List[str]) -> None:
        for row in rows:
            failures.append(
                {
                    "kind": kind,
                    "path": row.get("path"),
                    "url": row.get("url"),
                    "viewport": {"width": row.get("width"), "height": 900},
                    "details": {key: row.get(key) for key in detail_keys},
                }
            )

    add_failure("page_http_status_failed", bad_http_status, ["httpStatus", "title"])
    add_failure("page_error_shell_failed", bad_shell, ["hasAppShell", "title"])
    add_failure("page_error_shell_failed", error_pages, ["matchedErrorKeyword", "title"])
    add_failure("page_expected_dom_failed", wrong_paths, ["expectedPath"])
    add_failure("page_expected_dom_failed", missing_expected_texts, ["missingExpectedTexts"])
    add_failure("page_expected_dom_failed", missing_expected_ids, ["missingExpectedIds"])
    add_failure("page_expected_dom_failed", missing_required_toggles, ["missingRequiredToggleIds"])
    add_failure("page_overflow_failed", overflowing, ["maxScrollWidth", "scrollMetrics", "overflowOffenders"])
    add_failure("page_visual_contract_failed", overlapping_toggles, ["toggleOverlapCount"])
    add_failure("page_visual_contract_failed", bad_dark_summary, ["darkSummaryBadCount"])
    add_failure("page_visual_contract_failed", bad_dark_summary_contrast, ["darkLowContrastSummaryCount"])
    add_failure("page_visual_contract_failed", bad_dark_text_contrast, ["darkLowContrastTextCount"])
    add_failure("page_visual_contract_failed", bad_dark_notice, ["darkNoticeBadCount"])
    add_failure("page_visual_contract_failed", bad_logs_table, ["logsTableMultiline"])
    add_failure("page_visual_contract_failed", bad_multiline_tables, ["multilineTableChecks"])

    if not any(item["toggleCount"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible toggle rows found"}})
    if not any(item["visibleNotices"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible notices found"}})
    if failures:
        raise AssertionError(json.dumps(failures, ensure_ascii=False, indent=2, sort_keys=True))


def test_ui_browser_geometry_smoke_covers_scheduler_run_page() -> None:
    backup_signals = EXPECTED_PAGE_SIGNALS["/system/backup"]
    logs_signals = EXPECTED_PAGE_SIGNALS["/system/logs"]
    history_version_signals = EXPECTED_PAGE_SIGNALS["/system/history?version=2"]
    assert "/scheduler/?status=pending" in SMOKE_PATHS
    assert "/scheduler/batches?status=pending" not in SMOKE_PATHS
    assert "/system/history" in SMOKE_PATHS
    assert "/system/history?version=2" in SMOKE_PATHS
    assert any(path.startswith("/reports/?") for path in SMOKE_PATHS)
    assert any(path.startswith("/reports/overdue?") for path in SMOKE_PATHS)
    assert any(path.startswith("/reports/utilization?") for path in SMOKE_PATHS)
    assert any(path.startswith("/reports/execution-review?") for path in SMOKE_PATHS)
    assert any(path.startswith("/reports/downtime?") for path in SMOKE_PATHS)
    assert EXPECTED_PAGE_SIGNALS["/scheduler/?status=pending"]["ids"] == [
        "jsRunScheduleForm",
        "runEnforceReady",
        "runStrictMode",
    ]
    assert "pluginStatusTable" in cast(List[str], backup_signals["ids"])
    assert "启动问题" in cast(List[str], backup_signals["diagnostic_texts"])
    assert "详情格式异常" in cast(List[str], logs_signals["diagnostic_texts"])
    assert "当前版本的排产摘要读取失败" in cast(List[str], history_version_signals["diagnostic_texts"])
    assert EXPECTED_PAGE_SIGNALS["/system/history"]["ids"] == ["systemHistoryTable"]
    repo_root = Path(__file__).resolve().parents[1]
    probe_source = (repo_root / "tests" / "ui_geometry_probe_page_eval.mjs").read_text(encoding="utf-8")
    assert '"/scheduler/": ["runEnforceReady", "runStrictMode"]' in probe_source
    assert "multilineTableComputedOk('#systemLogsTable')" in probe_source
    assert "multilineTableComputedOk('#pluginStatusTable')" in probe_source
    assert "multilineTableComputedOk('#systemHistoryTable')" in probe_source
