"""SSR boot, local assets and retirement preservation; rendered geometry remains a real-browser obligation."""

from __future__ import annotations

import json
from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Set, Tuple
from urllib.parse import urlsplit

from tests._support.paths import REPO_ROOT
from tests.app_runtime.ui_geometry_browser_support import _build_app, _shutdown_app
from tests.app_runtime.ui_geometry_contract_data import (
    ERROR_PAGE_KEYWORDS,
    FULL_UI_CONTRACT_PATHS,
    GEOMETRY_CASES,
    geometry_scenarios,
)
from tests.app_runtime.ui_geometry_fixture_support import assert_geometry_retention, assert_retired_geometry_boundary

SMOKE_PATHS = FULL_UI_CONTRACT_PATHS


class _HtmlSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Set[str] = set()
        self.meta_names: Set[str] = set()
        self.tags: Set[str] = set()
        self.text_parts: List[str] = []
        self.title_parts: List[str] = []
        self.assets: List[Tuple[str, str]] = []
        self.boot_parts: List[str] = []
        self.root_state = ""
        self._in_title = False
        self._in_script = False
        self._in_boot = False

    def handle_starttag(self, tag: str, attrs: Iterable[Tuple[str, Optional[str]]]) -> None:
        self.tags.add(tag)
        attr_map: Dict[str, str] = {name: value or "" for name, value in attrs}
        if tag == "title":
            self._in_title = True
        if attr_map.get("id"):
            self.ids.add(attr_map["id"])
        if attr_map.get("id") == "root":
            self.root_state = attr_map.get("data-workbench-boot", "")
        if tag == "meta" and attr_map.get("name"):
            self.meta_names.add(attr_map["name"])
        if tag == "script":
            self._in_script = True
            self._in_boot = attr_map.get("id") == "workbench-boot" and attr_map.get("type") == "application/json"
            if attr_map.get("src"):
                self.assets.append((tag, attr_map["src"]))
        if tag == "link" and attr_map.get("rel") in ("stylesheet", "icon"):
            self.assets.append((tag, attr_map.get("href", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_script = self._in_boot = False

    def handle_data(self, data: str) -> None:
        if self._in_boot:
            self.boot_parts.append(data)
        if self._in_script:
            return
        text = data.strip()
        if text:
            self.text_parts.append(text)
            if self._in_title:
                self.title_parts.append(text)

    @property
    def visible_text(self) -> str:
        return "\n".join(self.text_parts)

    @property
    def title(self) -> str:
        return " ".join(self.title_parts)

    @property
    def boot(self):
        return json.loads("".join(self.boot_parts)) if self.boot_parts else None


def _parse_html(html: str) -> _HtmlSignalParser:
    parser = _HtmlSignalParser()
    parser.feed(html)
    return parser


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def _has_boot_shell(parsed):
    return ("root" in parsed.ids and "workbench-boot" in parsed.ids
            and parsed.root_state in ("loading", "ready") and isinstance(parsed.boot, dict)
            and parsed.boot.get("schema_version") == 1)


def _matched_error_keyword(html: str, parsed: _HtmlSignalParser, status_code: int) -> str:
    if status_code >= 500:
        for keyword in ERROR_PAGE_KEYWORDS:
            if _contains_keyword(html, keyword):
                return keyword
        return f"HTTP {status_code}"
    for keyword in ERROR_PAGE_KEYWORDS:
        if _contains_keyword(parsed.title, keyword):
            return keyword
    if _has_boot_shell(parsed):
        return ""
    lower_html = html.lower()
    if "werkzeug" in lower_html and ("traceback" in lower_html or "debugger" in lower_html):
        return "Werkzeug"
    for keyword in ERROR_PAGE_KEYWORDS:
        if _contains_keyword(parsed.visible_text, keyword):
            return keyword
    return ""


def test_error_keyword_detector_does_not_flag_normal_app_shell_log_text() -> None:
    html = """
    <html><head><title>系统管理 - 操作日志</title></head><body>
      <div id="root" data-workbench-boot="ready"><header class="top-header">系统</header>
        <nav class="sidebar-nav">工作台</nav><main>Traceback in old Werkzeug log row</main></div>
      <script id="workbench-boot" type="application/json">{"schema_version":1,"view":"system"}</script>
    </body></html>
    """
    parsed = _parse_html(html)
    assert _has_boot_shell(parsed)
    assert _matched_error_keyword(html, parsed, 200) == ""


def test_error_keyword_detector_flags_error_page_title() -> None:
    html = "<html><head><title>Internal Server Error</title></head><body>broken</body></html>"
    parsed = _parse_html(html)
    assert _matched_error_keyword(html, parsed, 200) == "Internal Server Error"
    assert not _has_boot_shell(parsed)


def test_ui_geometry_contract_includes_first_version_workbench_pages() -> None:
    assert set(SMOKE_PATHS) == {"/workbench?view=" + view for view in (
        "dashboard", "run", "analysis", "gantt", "field", "batches", "system", "process", "reports", "review",
    )}
    assert all(case["selectors"] and case["texts"] for case in GEOMETRY_CASES)
    cases = {case["case"]: case for case in GEOMETRY_CASES}
    assert cases["gantt-machine"]["dimension"] == "machine" and cases["gantt-operator"]["dimension"] == "operator"
    assert cases["plan-invalid-summary"]["action"] == "invalid-history"
    assert cases["plugin-startup-audit"]["plugin_audit"]
    assert all(cases[name]["report_scope"] for name in (
        "reports-overview", "reports-overdue", "reports-utilization", "reports-execution", "reports-downtime",
    ))


def _assert_local_boot(html, parsed, case):
    assert _has_boot_shell(parsed), case["case"]
    assert parsed.root_state == "loading", case["case"]
    assert parsed.boot["view"] == case["view"]
    assert parsed.boot["navigation"] == case["navigation"]
    assert case["view"] in parsed.boot["enabled_views"]
    assert parsed.boot["titles"][case["view"]] in parsed.title
    assert parsed.boot["entry_url"] == "/workbench"
    assert parsed.boot["overview_url"] == "/api/workbench/v1/system/overview"
    assert "viewport" in parsed.meta_names
    assert any(tag == "script" for tag, _ in parsed.assets) and any(tag == "link" for tag, _ in parsed.assets)
    for _, uri in parsed.assets:
        target = urlsplit(uri)
        assert not target.scheme and not target.netloc and target.path.startswith("/static/workbench/"), uri
        assert (REPO_ROOT / "static" / target.path[len("/static/"):]).is_file(), uri
    assert _matched_error_keyword(html, parsed, 200) == "", case["case"]


def test_ui_smoke_pages_render_expected_html_contract(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    try:
        assert_retired_geometry_boundary(app)
        scenarios = geometry_scenarios(app.extensions["ui_geometry_evidence"]["identity"])
        for case in scenarios:
            response = app.test_client().get(case["path"], follow_redirects=False)
            try:
                assert response.status_code == 200, case["case"]
                html = response.get_data(as_text=True)
                _assert_local_boot(html, _parse_html(html), case)
            finally:
                response.close()
        assert_geometry_retention(app)
    finally:
        _shutdown_app(app)
