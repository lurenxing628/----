from __future__ import annotations

import importlib
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from flask import render_template_string

REPO_ROOT = Path(__file__).resolve().parents[1]


class _WorkbenchMenuParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: List[Tuple[str, str]] = []
        self.anchor_hrefs: List[str] = []
        self.tags: List[str] = []
        self.attrs: List[Tuple[str, str, str]] = []
        self._current_link: Optional[Dict[str, object]] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        self.tags.append(tag)
        attr_map = {name.lower(): value or "" for name, value in attrs}
        for name, value in attr_map.items():
            self.attrs.append((tag, name, value))
        if tag == "a":
            self.anchor_hrefs.append(attr_map.get("href", ""))
            if "aps-workbench-nav-link" in attr_map.get("class", "").split():
                self._current_link = {"href": attr_map.get("href", ""), "text": []}

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._current_link is not None:
            text_parts = self._current_link.get("text", [])
            text = " ".join("".join(text_parts).split()) if isinstance(text_parts, list) else ""
            self.links.append((str(self._current_link.get("href", "")), text))
            self._current_link = None

    def handle_data(self, data: str) -> None:
        if self._current_link is not None:
            text_parts = self._current_link.setdefault("text", [])
            if isinstance(text_parts, list):
                text_parts.append(data)


def _parse_workbench_menu(html: str) -> _WorkbenchMenuParser:
    parser = _WorkbenchMenuParser()
    parser.feed(html)
    return parser


def _read(rel_path: str) -> str:
    return (REPO_ROOT / rel_path).read_text(encoding="utf-8")


def _render_workbench_menu() -> str:
    app_mod = importlib.import_module("app")
    app = app_mod.create_app()
    with app.test_request_context("/"):
        return render_template_string(
            '{% import "components/ui_macros.html" as ui %}{{ ui.workbench_nav_menu() }}'
        )


def test_base_header_mounts_plan_workbench_menu() -> None:
    base = _read("templates/base.html")

    assert "{{ ui.workbench_nav_menu() }}" in base
    assert "计划工作台" not in base, "顶层菜单文案应由 UI 宏统一维护，base.html 只负责挂载"


def test_workbench_menu_renders_six_core_destinations() -> None:
    html = _render_workbench_menu()
    parser = _parse_workbench_menu(html)

    expected_pairs = [
        ("首页值班台", "/"),
        ("排产分析", "/scheduler/analysis"),
        ("设备甘特图", "/scheduler/gantt?view=machine"),
        ("人员甘特图", "/scheduler/gantt?view=operator"),
        ("资源派工", "/scheduler/resource-dispatch"),
        ("计划和现场实际", "/reports/execution-review"),
    ]
    assert "计划工作台" in html
    assert parser.anchor_hrefs == [href for _label, href in expected_pairs]
    assert len(parser.links) == len(expected_pairs), "计划工作台菜单只能有这 6 个只读入口"
    assert [href for href, _text in parser.links] == [href for _label, href in expected_pairs]
    for (label, _href), (_actual_href, text) in zip(expected_pairs, parser.links):
        assert label in text


def test_workbench_menu_is_readonly_and_hides_internal_fields() -> None:
    html = _render_workbench_menu()
    parser = _parse_workbench_menu(html)
    forbidden_fragments = (
        "plan_role",
        "scenario_id",
        "source_table",
        "candidate_id",
        "op_id",
        "schedule_id",
        "actual-template",
        "actual-import",
        "actual-write",
        "formaction=",
        "javascript:",
        "data-actual-record-url-template",
        "导入",
        "模板下载",
    )

    lower_html = html.lower()
    for fragment in forbidden_fragments:
        assert fragment.lower() not in lower_html

    forbidden_tags = {
        "base",
        "button",
        "embed",
        "form",
        "iframe",
        "input",
        "link",
        "object",
        "script",
        "select",
        "style",
        "textarea",
    }
    assert forbidden_tags.isdisjoint(set(parser.tags))

    for tag, attr_name, value in parser.attrs:
        assert not attr_name.startswith("data-"), (tag, attr_name, value)
        assert not attr_name.startswith("on"), (tag, attr_name, value)
        assert attr_name not in {"download", "method", "formaction"}, (tag, attr_name, value)
        assert "javascript:" not in value.lower(), (tag, attr_name, value)
        if tag == "a" and attr_name == "href":
            assert value in {href for href, _text in parser.links}, value


def test_workbench_menu_uses_local_css_and_no_javascript_dependency() -> None:
    macro = _read("templates/components/ui_macros.html")
    css = _read("static/css/ui_contract.css")

    assert "<details class=\"aps-workbench-nav" in macro
    assert "<summary class=\"aps-workbench-nav-summary\">" in macro
    assert "aps-workbench-nav-menu" in css
    assert "aps-workbench-nav-link" in css

    combined = macro + css
    for external in ("https://", "http://", "cdn", "unpkg", "fonts.googleapis", "cdnjs"):
        assert external not in combined
