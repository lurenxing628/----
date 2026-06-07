"""回归测试：不依赖真实浏览器，用 HTMLParser 解析各 UI 页面 HTML，断言其满足契约——含 aps-ui-template-env meta、apsThemeToggle id 与 nav/header 即视为正常 app shell（不误报错误页），缺 shell 或标题/正文命中错误关键词则判为错误页；并校验 SMOKE_PATHS 覆盖首版本工作台各页，每页 HTTP 200、含期望文本/id、不含禁止文本。"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Dict, Iterable, List, Optional, Set, Tuple

from tests.app_runtime.ui_geometry_browser_support import _build_app
from tests.app_runtime.ui_geometry_contract_data import (
    ERROR_PAGE_KEYWORDS,
    EXPECTED_PAGE_SIGNALS,
    FULL_UI_CONTRACT_PATHS,
)

SMOKE_PATHS = FULL_UI_CONTRACT_PATHS


class _HtmlSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Set[str] = set()
        self.meta_names: Set[str] = set()
        self.tags: Set[str] = set()
        self.text_parts: List[str] = []
        self.title_parts: List[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: Iterable[Tuple[str, Optional[str]]]) -> None:
        self.tags.add(tag)
        if tag == "title":
            self._in_title = True
        attr_map: Dict[str, str] = {name: value or "" for name, value in attrs}
        if attr_map.get("id"):
            self.ids.add(attr_map["id"])
        if tag == "meta" and attr_map.get("name"):
            self.meta_names.add(attr_map["name"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
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


def _parse_html(html: str) -> _HtmlSignalParser:
    parser = _HtmlSignalParser()
    parser.feed(html)
    return parser


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword.lower() in text.lower()


def _matched_error_keyword(html: str, parsed: _HtmlSignalParser, status_code: int) -> str:
    if status_code >= 500:
        for keyword in ERROR_PAGE_KEYWORDS:
            if _contains_keyword(html, keyword):
                return keyword
        return f"HTTP {status_code}"
    for keyword in ERROR_PAGE_KEYWORDS:
        if _contains_keyword(parsed.title, keyword):
            return keyword
    has_app_shell = (
        "aps-ui-template-env" in parsed.meta_names
        and "apsThemeToggle" in parsed.ids
        and ("nav" in parsed.tags or "header" in parsed.tags)
    )
    if has_app_shell:
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
    <html>
      <head><title>系统管理 - 操作日志</title><meta name="aps-ui-template-env" content="v2"></head>
      <body><header><nav>系统</nav></header><button id="apsThemeToggle">主题</button><main>Traceback in old Werkzeug log row</main></body>
    </html>
    """
    parsed = _parse_html(html)

    assert _matched_error_keyword(html, parsed, 200) == ""


def test_error_keyword_detector_flags_error_page_title() -> None:
    html = "<html><head><title>Internal Server Error</title></head><body>broken</body></html>"
    parsed = _parse_html(html)

    assert _matched_error_keyword(html, parsed, 200) == "Internal Server Error"


def test_ui_geometry_contract_includes_first_version_workbench_pages() -> None:
    workbench_paths = {
        "/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "/scheduler/analysis?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "/scheduler/gantt?view=machine&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=M_UI_GEOMETRY",
        "/scheduler/gantt?view=operator&version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&gantt_batch=B_UI_GEOMETRY&gantt_resource=O_UI_GEOMETRY",
        "/scheduler/resource-dispatch?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&scope_type=machine&machine_id=M_UI_GEOMETRY&batch_id=B_UI_GEOMETRY",
        "/reports/?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "/reports/overdue?version=1&plan_role=adopted&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
        "/reports/utilization?version=1&plan_role=adopted&start_date=2026-05-06&end_date=2026-05-06&resource_type=operator&resource_id=O_UI_GEOMETRY",
        "/reports/execution-review?version=1&date_from=2026-05-06&date_to=2026-05-06&batch_id=B_UI_GEOMETRY&resource_type=machine&resource_id=M_UI_GEOMETRY",
    }

    assert workbench_paths.issubset(set(SMOKE_PATHS))


def test_ui_smoke_pages_render_expected_html_contract(tmp_path, monkeypatch) -> None:
    app = _build_app(tmp_path, monkeypatch)
    client = app.test_client()

    for page_path in SMOKE_PATHS:
        response = client.get(page_path)
        html = response.get_data(as_text=True)
        parsed = _parse_html(html)
        expected = EXPECTED_PAGE_SIGNALS[page_path]

        assert response.status_code == 200, page_path
        assert "aps-ui-template-env" in parsed.meta_names, page_path
        assert "apsThemeToggle" in parsed.ids, page_path
        assert "nav" in parsed.tags or "header" in parsed.tags, page_path
        matched_error = _matched_error_keyword(html, parsed, response.status_code)
        assert matched_error == "", f"{page_path}: matched error keyword {matched_error}"
        for text in expected.get("stable_texts") or ():
            assert text in parsed.visible_text, f"{page_path}: missing text {text}"
        for text in expected.get("forbidden_texts") or ():
            assert text not in parsed.visible_text, f"{page_path}: forbidden text {text}"
        for element_id in expected["ids"]:
            assert element_id in parsed.ids, f"{page_path}: missing id {element_id}"
