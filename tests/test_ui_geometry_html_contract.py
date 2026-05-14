from __future__ import annotations

from html.parser import HTMLParser
from typing import Dict, Iterable, Set

from tests.regression_ui_browser_geometry_smoke import EXPECTED_PAGE_SIGNALS, SMOKE_PATHS, _build_app


class _HtmlSignalParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: Set[str] = set()
        self.meta_names: Set[str] = set()
        self.tags: Set[str] = set()
        self.text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: Iterable[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        attr_map: Dict[str, str] = {name: value or "" for name, value in attrs}
        if attr_map.get("id"):
            self.ids.add(attr_map["id"])
        if tag == "meta" and attr_map.get("name"):
            self.meta_names.add(attr_map["name"])

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.text_parts.append(text)

    @property
    def visible_text(self) -> str:
        return "\n".join(self.text_parts)


def _parse_html(html: str) -> _HtmlSignalParser:
    parser = _HtmlSignalParser()
    parser.feed(html)
    return parser


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
        assert "Traceback" not in html, page_path
        assert "Internal Server Error" not in html, page_path
        assert "Werkzeug" not in html, page_path
        for text in expected["texts"]:
            assert text in parsed.visible_text, f"{page_path}: missing text {text}"
        for element_id in expected["ids"]:
            assert element_id in parsed.ids, f"{page_path}: missing id {element_id}"
