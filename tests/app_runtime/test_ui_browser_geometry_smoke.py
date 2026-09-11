"""Real current-UI geometry, with retired controls excluded and data/audit retention checked separately."""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List

import pytest

from tests._support.paths import REPO_ROOT
from tests.app_runtime.ui_geometry_browser_support import (
    EXPECTED_PAGE_SIGNALS,
    SMOKE_PATHS,
    _build_app,
    _find_chrome,
    _find_node_with_browser_runtime,
    _run_chrome_geometry_probe,
    _serve_app,
    _shutdown_app,
    _shutdown_served_app,
)
from tests.app_runtime.ui_geometry_contract_data import (
    GEOMETRY_CASES,
    READY_RADIOS,
    RESOURCE_RADIOS,
    RETIRED_GEOMETRY,
    geometry_scenarios,
)
from tests.app_runtime.ui_geometry_fixture_support import assert_geometry_retention, assert_retired_geometry_boundary


@pytest.mark.skipif(
    bool(os.environ.get("CI")),
    reason=(
        "CI runner 的 headless Chrome 无法在超时内建立 DevTools CDP 端口"
        "（chrome_devtools_port_timeout，实测 chrome 启动后 ~10s 仍无 DevToolsActivePort）；"
        "真实浏览器渲染冒烟留给本地/部署机，env 探测契约由 test_ui_browser_geometry_env.py 守护。"
    ),
)
def test_ui_pages_do_not_create_body_level_overflow_in_real_browser(tmp_path, monkeypatch) -> None:
    chrome = _find_chrome()
    node = _find_node_with_browser_runtime()
    deadline = time.monotonic() + 90
    results, scenarios = [], []
    # The invalid-history catalog must not replace the real current v1 used by execution views.
    for invalid_history in (False, True):
        root = tmp_path / ("invalid-history" if invalid_history else "current-plan")
        measured, cases = _run_geometry_phase(root, monkeypatch, chrome, node, deadline, invalid_history)
        results.extend(measured)
        scenarios.extend(cases)
    expected_pairs = {(case["case"], width) for case in scenarios for width in (1024, 768)}
    assert len(results) == len(expected_pairs)
    assert {(item["case"], item["width"]) for item in results} == expected_pairs
    assert {case["case"] for case in scenarios} == {case["case"] for case in GEOMETRY_CASES}
    _assert_geometry_results(results, scenarios)


def _run_geometry_phase(tmp_path, monkeypatch, chrome, node, deadline, invalid_history):
    app = _build_app(tmp_path, monkeypatch, invalid_history=invalid_history)
    served = None
    history_cases = {"plan-history", "plan-invalid-summary"}
    scenarios = [case for case in geometry_scenarios(app.extensions["ui_geometry_evidence"]["identity"])
                 if (case["case"] in history_cases) == invalid_history]
    try:
        assert_retired_geometry_boundary(app)
        served = _serve_app(app)
        results = _run_chrome_geometry_probe(
            chrome_path=chrome.chrome_path, node_path=node.node_path, base_url=served.base_url,
            tmp_path=tmp_path, scenarios=scenarios, deadline=deadline, chrome_info=chrome, node_info=node,
        )
        assert_geometry_retention(app)
    finally:
        try:
            if served is not None:
                _shutdown_served_app(served)
        finally:
            _shutdown_app(app)
    return results, scenarios


def _assert_geometry_results(results, scenarios):
    overflowing = [item for item in results if item["bodyOverflow"]]
    overlapping_toggles = [item for item in results if item["toggleOverlapCount"]]
    bad_dark_summary = [item for item in results if item["darkSummaryBadCount"]]
    bad_dark_summary_contrast = [item for item in results if item["darkLowContrastSummaryCount"]]
    bad_dark_text_contrast = [item for item in results if item["darkLowContrastTextCount"]]
    bad_dark_notice = [item for item in results if item["darkNoticeBadCount"]]
    bad_multiline_text = [item for item in results if any(not row["ok"] for row in item["multilineTextDetails"])]
    missing_visual_samples = [item for item in results if item["missingVisualSamples"]]
    bad_theme = [item for item in results if not item["darkTheme"]]
    bad_plugin_audit = [item for item in results if item["pluginAudit"] is not None
                       and not all(item["pluginAudit"][key] for key in
                                   ("publicBodyMatches", "privateCanaryAbsent", "truncationMarkerAbsent"))]
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
                    "case": row.get("case"),
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
    add_failure("page_visual_contract_failed", bad_multiline_text, ["multilineTextDetails"])
    add_failure("page_visual_contract_failed", missing_visual_samples, ["missingVisualSamples"])
    add_failure("page_visual_contract_failed", bad_theme, ["darkTheme"])
    add_failure("page_expected_dom_failed", bad_plugin_audit, ["pluginAudit"])
    add_failure("page_visual_contract_failed", bad_multiline_tables, ["multilineTableChecks", "multilineTableDetails"])

    by_case = {case["case"]: case for case in scenarios}
    for item in results:
        expected = by_case[item["case"]]
        assert set(item["multilineTableChecks"]) == set(expected.get("tables", []))
        assert {row["selector"] for row in item["multilineTextDetails"]} == set(expected.get("multiline", []))
        assert item["toggleCount"] == sum(expected.get("controls", {}).values())
        for table in item["multilineTableDetails"]:
            if table["selector"] == ".sm-logs-table":
                assert table["fixedLogHeaders"] and table["headerTexts"] == [
                    "工厂本地时间", "类型", "状态", "级别", "摘要 / 来源", "详情",
                ]
    if not any(item["darkSummaryCount"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible summaries found"}})
    if not any(item["toggleCount"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible toggle rows found"}})
    if not any(item["visibleNotices"] > 0 for item in results):
        failures.append({"kind": "page_expected_dom_failed", "details": {"message": "no visible notices found"}})
    if failures:
        raise AssertionError(json.dumps(failures, ensure_ascii=False, indent=2, sort_keys=True))


def test_ui_browser_geometry_smoke_covers_scheduler_run_page() -> None:
    assert "/workbench?view=run" in SMOKE_PATHS
    assert "/workbench?view=system" in SMOKE_PATHS
    assert len(GEOMETRY_CASES) == len(EXPECTED_PAGE_SIGNALS) == 20
    assert EXPECTED_PAGE_SIGNALS["run-preflight"]["controls"] == {READY_RADIOS: 2, RESOURCE_RADIOS: 2}
    assert EXPECTED_PAGE_SIGNALS["plan-invalid-summary"]["action"] == "invalid-history"
    assert {EXPECTED_PAGE_SIGNALS[key]["catalog"] for key in
            ("reports-overdue", "reports-utilization", "reports-downtime")} == {"overdue", "utilization", "downtime"}
    assert EXPECTED_PAGE_SIGNALS["reports-execution"]["view"] == "review"
    assert EXPECTED_PAGE_SIGNALS["plugin-startup-audit"]["plugin_audit"] is True
    assert EXPECTED_PAGE_SIGNALS["plugin-startup-audit"]["log_summary"] == "扩展功能管理 · 其他操作（load）"
    assert RETIRED_GEOMETRY["scheduler.config"]["geometry_counted"] is False
    assert RETIRED_GEOMETRY["pluginStatusTable"]["geometry_counted"] is False
    assert set(RETIRED_GEOMETRY["scheduler.config"]["controls"]) == {
        "freezeWindowEnabled", "preferPrimarySkill", "enforceReadyDefault", "autoAssignEnabled", "orToolsEnabled",
    }
    assert all("pluginStatusTable" not in selector and "sm-check-table" not in selector
               for case in GEOMETRY_CASES for selector in case["selectors"])
    probe_source = (REPO_ROOT / "tests/ui_geometry_probe_page_eval.mjs").read_text(encoding="utf-8")
    assert "multilineTableComputedOk" in probe_source
    assert "CSSTransition" in probe_source and "animation.finished" in probe_source
    assert "contrastText.filter(lowContrast)" in probe_source
    assert "maxScrollWidth > innerWidth + 1" in probe_source
    assert "document.documentElement.setAttribute" not in probe_source
