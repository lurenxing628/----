"""回归测试：说明书页“本页说明”通道——顶栏「帮助」带 ``page=<视图 id>`` 与 ``src=<返回地址>`` 打开时，15 个视图都能先显示自己那一章（只截到下一个同级或更高级标题），“返回刚才页面”回到 src、没有安全 src 时回到该视图本身，“下载整本说明书”保留 page 与 src，“阅读整本说明书”带章节锚点；未登记的 page 退化为整本并提示但不回显页面标识；说明书文件读不到时页面仍能打开并把 ``manual_available`` 传给模板。"""

from __future__ import annotations

from html.parser import HTMLParser
from typing import Dict, List, Tuple
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import template_rendered

import web.routes.workbench.manual_page as route_mod
from tests._support.paths import REPO_ROOT
from web.viewmodels.page_manuals_registry import MANUAL_VIEW_IDS, VIEW_MANUALS

MANUAL_PATH = REPO_ROOT / "static/docs/scheduler_manual.md"
MANUAL_URL = "/scheduler/config/manual"
DOWNLOAD_URL = "/scheduler/config/manual/download"


class Page(HTMLParser):
    def __init__(self, text: str):
        super().__init__(convert_charrefs=True)
        self.links: List[Tuple[str, str]] = []
        self.ids: set = set()
        self.title = ""
        self._link: List[str] = []
        self._in_title = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a":
            self._link = [attrs.get("href") or ""]
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag):
        if tag == "a" and self._link:
            self.links.append((self._link[0], "".join(self._link[1:]).strip()))
            self._link = []
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._link:
            self._link.append(data)
        if self._in_title:
            self.title += data

    def href(self, label: str) -> str:
        matches = [href for href, text in self.links if text == label]
        assert len(matches) == 1, (label, self.links)
        return matches[0]


def _view_url(view: str) -> str:
    return "/workbench/trial" if view == "trial" else "/workbench?view=" + view


def _render(client, url: str) -> Tuple[str, Page, Dict]:
    captured: List[Dict] = []

    def rendered(sender, template, context, **extra):
        captured.append(context)

    app = client.application
    template_rendered.connect(rendered, app, weak=False)
    try:
        response = client.get(url)
    finally:
        template_rendered.disconnect(rendered, app)
    html = response.get_data(as_text=True)
    assert response.status_code == 200, html
    assert len(captured) == 1, len(captured)
    return html, Page(html), captured[0]


def _query(url: str) -> Dict[str, List[str]]:
    return parse_qs(urlsplit(url).query, keep_blank_values=True)


def test_manual_uses_current_operator_and_calibration_status_labels() -> None:
    manual = MANUAL_PATH.read_text(encoding="utf-8")
    assert "人员状态有在岗、请假、停用" in manual
    assert "人员状态有启用" not in manual
    assert "状态（数据不足 / 已有建议）" in manual
    assert "状态（数据不足 / 待复核）" not in manual


def test_every_registered_view_opens_its_own_section(app_client) -> None:
    manual_text = MANUAL_PATH.read_text(encoding="utf-8")
    sections = route_mod._manual_section_map(manual_text)
    for view in MANUAL_VIEW_IDS:
        entry = VIEW_MANUALS[view]
        src = _view_url(view)
        html, page, context = _render(app_client, MANUAL_URL + "?page=" + view + "&src=" + src)
        assert context["manual_mode"] == "page" and context["manual_available"] is True, view
        assert context["current_manual"]["view"] == view and context["title"] == "本页说明 - " + entry["title"], view
        assert "本页说明 - " + entry["title"] in page.title, view
        assert route_mod.PAGE_NOT_REGISTERED_WARNING not in html and route_mod.PAGE_SECTION_MISSING_WARNING not in html, view
        section = sections[entry["heading"]]
        assert context["fallback_text"] == section["source"], view
        assert section["anchor"] in page.ids, view
        # 只截当前章节：别的登记章节只有作为子章节（比如 5. 数据准备里的 5.8）时才会出现在本页说明里。
        for other_view, other in VIEW_MANUALS.items():
            if other_view == view:
                continue
            child = sections[other["heading"]]["source"] in section["source"]
            assert (sections[other["heading"]]["anchor"] in page.ids) == child, (view, other_view)
        assert page.href("返回刚才页面") == src, view
        download = page.href("下载整本说明书")
        assert urlsplit(download).path == DOWNLOAD_URL and _query(download) == {"page": [view], "src": [src]}, view
        full = page.href("阅读整本说明书")
        assert urlsplit(full).path == MANUAL_URL and urlsplit(full).fragment == section["anchor"], view
        assert _query(full) == {"src": [src]}, view
        related = context["related_manuals"]
        assert [item["view"] for item in related] == list(entry["related"]), view
        for item in related:
            link = page.href(item["title"])
            assert urlsplit(link).path == MANUAL_URL and _query(link) == {"page": [item["view"]], "src": [src]}, (view, item)
            assert item["full_manual_section_url"].endswith("#" + sections[VIEW_MANUALS[item["view"]]["heading"]]["anchor"]), (view, item)


def test_run_manual_section_contains_run_history_instructions(app_client) -> None:
    html, _page, context = _render(app_client, MANUAL_URL + "?page=run&src=" + _view_url("analysis"))
    assert context["manual_mode"] == "page" and context["current_manual"]["view"] == "run"
    assert "排产记录" in context["fallback_text"] and "这里不能导出" in context["fallback_text"]
    assert route_mod.PAGE_NOT_REGISTERED_WARNING not in html


@pytest.mark.parametrize("view", ("dashboard", "trial", "gantt"))
def test_page_without_src_returns_to_the_view_itself(app_client, view: str) -> None:
    html, page, context = _render(app_client, MANUAL_URL + "?page=" + view)
    assert context["manual_mode"] == "page"
    assert page.href("返回" + VIEW_MANUALS[view]["title"]) == _view_url(view)
    assert "返回刚才页面" not in html
    assert _query(page.href("下载整本说明书")) == {"page": [view]}
    assert _query(page.href("阅读整本说明书")) == {}


def test_unsafe_src_is_dropped_and_never_echoed(app_client) -> None:
    html, page, _context = _render(app_client, MANUAL_URL + "?page=field&src=http://evil.example/x")
    assert page.href("返回现场记录") == _view_url("field")
    assert "evil.example" not in html


def test_unknown_page_falls_back_to_full_manual_with_notice(app_client) -> None:
    src = _view_url("dashboard")
    html, page, context = _render(app_client, MANUAL_URL + "?page=nope.page&src=" + src)
    assert context["manual_mode"] == "full" and context["current_manual"] is None and context["related_manuals"] == []
    assert context["title"] == route_mod.FULL_MANUAL_TITLE and "本页说明 -" not in page.title
    assert route_mod.PAGE_NOT_REGISTERED_WARNING in html and "nope.page" not in html
    assert page.href("返回刚才页面") == src
    assert _query(page.href("下载说明书原文")) == {"src": [src]}
    assert context["manual_text"] == MANUAL_PATH.read_text(encoding="utf-8")


def test_download_keeps_page_and_src_and_redirects_when_file_missing(app_client, monkeypatch) -> None:
    src = _view_url("field")
    download = app_client.get(DOWNLOAD_URL + "?page=field&src=" + src)
    assert download.status_code == 200 and "attachment" in download.headers["Content-Disposition"]
    assert download.data == MANUAL_PATH.read_bytes()
    download.close()
    with monkeypatch.context() as patch:
        patch.setattr(route_mod, "_resolve_scheduler_manual_md_path", lambda: (None, ["/nonexistent/scheduler_manual.md"]))
        redirected = app_client.get(DOWNLOAD_URL + "?page=field&src=" + src)
    assert redirected.status_code == 302
    location = redirected.headers["Location"]
    assert urlsplit(location).path == MANUAL_URL and _query(location) == {"page": ["field"], "src": [src]}


def test_unavailable_manual_still_opens_page_request(app_client, monkeypatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(route_mod, "_resolve_scheduler_manual_md_path", lambda: (None, ["/nonexistent/scheduler_manual.md"]))
        html, page, context = _render(app_client, MANUAL_URL + "?page=field")
    assert context["manual_available"] is False and context["manual_mode"] == "full"
    assert context["download_url"] is None and "找不到说明书文件" in html
    assert route_mod.PAGE_SECTION_MISSING_WARNING not in html
    assert page.href("返回现场记录") == _view_url("field")


def test_heading_drift_degrades_to_full_manual_with_notice(app_client, monkeypatch) -> None:
    with monkeypatch.context() as patch:
        patch.setattr(route_mod, "_load_manual_source", lambda *_: ("# 系统使用说明\n\n## 1. 无关章节\n\n正文\n", None, True))
        html, page, context = _render(app_client, MANUAL_URL + "?page=field&src=" + _view_url("field"))
    assert context["manual_mode"] == "full" and context["manual_available"] is True
    assert route_mod.PAGE_SECTION_MISSING_WARNING in html and "本页说明 -" not in page.title


def test_manual_quote_rendering_stops_at_the_next_block_and_preserves_inline_text() -> None:
    from web.routes.workbench.legacy_presentation import render_manual_markdown

    rendered = render_manual_markdown("> **先检查**\n  > `参数` <原值>\n普通段落\n\n> 第二段引文")
    assert rendered == (
        "<blockquote><p><strong>先检查</strong><code>参数</code> &lt;原值&gt;</p></blockquote>"
        "<p>普通段落</p><blockquote><p>第二段引文</p></blockquote>"
    )
    assert render_manual_markdown(">\n正文") == "<blockquote><p></p></blockquote><p>正文</p>"
