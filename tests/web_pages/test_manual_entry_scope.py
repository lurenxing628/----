"""Retained manual pages keep full/page scope, exact source text and safe downloads.

The old floating help popover is retired. The current standalone manual must
still cover every registered page without losing its original return context.
"""

from __future__ import annotations

import html
import importlib
import re
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, quote, urlsplit

from flask import url_for

from tests._support.excel_templates import point_env_at_shared
from tests._support.gantt_retirement import _business_state
from tests._support.paths import REPO_ROOT
from tests._support.workbench_web_contract import canonical_boot

LEGACY_EXCEL_ENTRY_TERMS = (
    "零件工艺路线（Excel导入/导出）", "零件工序工时（Excel导入/导出）",
    "人员基本信息（Excel导入/导出）", "设备信息（Excel导入/导出）",
    "人员设备关联（Excel）", "设备人员关联（Excel）",
    "Excel 导入/导出", "Excel导入/导出", "Excel 导入导出", "Excel导入导出",
)


class _ManualHTML(HTMLParser):
    """Collect source text, safe links and unique anchors from the served manual."""

    def __init__(self, body):
        super().__init__()
        self.text, self.links, self.ids = [], [], []
        self._skip, self._anchor = None, None
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ("script", "style"):
            self._skip = tag
        if attrs.get("id"):
            self.ids.append(attrs["id"])
        if tag == "a":
            self._anchor = [attrs.get("href", ""), []]

    def handle_endtag(self, tag):
        if tag == self._skip:
            self._skip = None
        if tag == "a" and self._anchor is not None:
            self.links.append((self._anchor[0], "".join(self._anchor[1]).strip()))
            self._anchor = None

    def handle_data(self, value):
        if not self._skip:
            self.text.append(value)
            if self._anchor is not None:
                self._anchor[1].append(value)


def _url(app, endpoint, **values):
    """Build a local URL through the actual Flask registry."""
    with app.test_request_context():
        return url_for(endpoint, **values)


def _page(client, **query):
    """Require the standalone manual, unique anchors and local navigation."""
    response = client.get("/scheduler/config/manual", query_string=query)
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.headers["Cache-Control"] == "no-store"
    body = response.get_data(as_text=True)
    assert 'aria-label="说明书正文"' in body and 'class="manual-source"' in body
    assert 'data-workbench-legacy-response="true"' in body
    assert "floating-manual-btn" not in body and "scheduler-subnav-main" not in body
    parsed = _ManualHTML(body)
    assert len(parsed.ids) == len(set(parsed.ids))
    for href, _label in parsed.links:
        assert not urlsplit(href).scheme and not urlsplit(href).netloc
    for href, _label in parsed.links:
        if href.startswith("#"):
            assert href[1:] in parsed.ids
    return parsed, body


def _markdown_pieces(line):
    """Drop the Markdown markers the page now renders, keep every readable piece."""
    raw = line.strip()
    if not raw or re.match(r"^(?:\|[\s:|-]+\|$|-{3,}$|\*{3,}$|_{3,}$|```)", raw):
        return ()
    body = re.sub(r"^(?:#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)", "", raw)
    cells = body.strip("|").split("|") if raw.startswith("|") else [body]
    return tuple(cell.strip().replace("**", "").replace("`", "") for cell in cells)


def _source_visible(parsed, source):
    """Every retained Markdown line must remain visible, not just a short excerpt."""
    text = "".join(parsed.text)
    for line in source.splitlines():
        for expected in _markdown_pieces(line):
            if expected:
                assert expected in text, expected


def _link(parsed, label):
    """Require an explicitly named action in the parsed manual."""
    values = [href for href, text in parsed.links if text == label]
    assert values, (label, parsed.links)
    return values[0]


def _check_entry_terms(source):
    """Keep the public bulk-maintenance vocabulary, including historical notes."""
    for line in source.splitlines():
        for term in LEGACY_EXCEL_ENTRY_TERMS:
            if term in ("Excel 导入导出", "Excel导入导出") and all(value in line for value in ("老资料", "旧入口", "批量维护")):
                continue
            assert term not in line
    assert "批量维护" in source


def main(monkeypatch) -> None:
    directory = Path(tempfile.mkdtemp(prefix="aps-manual-scope-"))
    for env, leaf in (("APS_DB_PATH", "fixture.db"), ("APS_LOG_DIR", "logs"), ("APS_BACKUP_DIR", "backups")):
        monkeypatch.setenv(env, str(directory / leaf))
    monkeypatch.setenv("APS_ENV", "development")
    monkeypatch.setenv("SECRET_KEY", "aps-manual-entry-scope")
    point_env_at_shared(monkeypatch)
    app = importlib.import_module("app").create_app()
    client = app.test_client()
    manuals = importlib.import_module("web.viewmodels.page_manuals")
    raw = (REPO_ROOT / "static/docs/scheduler_manual.md").read_text(encoding="utf-8")
    _check_entry_terms(raw)
    canonical_boot(client, "/", "dashboard", {})
    # Normal legacy requests initialize maintenance defaults; freeze after that existing lifecycle step.
    before = _business_state(client)

    endpoints = sorted({rule.endpoint for rule in app.url_map.iter_rules()
                        if rule.endpoint in manuals.ENDPOINT_TO_MANUAL_ID and "GET" in rule.methods and not rule.arguments})
    assert endpoints
    for endpoint in endpoints:
        path = _url(app, endpoint)
        src = path if "?" in path else path + "?"
        parsed, body = _page(client, page=endpoint, src=src)
        manual = manuals.build_manual_for_endpoint(endpoint, include_sections=True)
        assert "本页说明 - " + manual["title"] in "".join(parsed.text)
        _source_visible(parsed, manuals.build_page_fallback_text(endpoint))
        assert _link(parsed, "返回刚才页面") == src
        download = _link(parsed, "下载整本说明书")
        query = parse_qs(urlsplit(download).query, keep_blank_values=True)
        assert query["page"] == [endpoint] and query["src"] == [src]
        assert "Win7 单机版" not in body and "sidebar-footnote" not in body

    for source in ("/material/materials?", "/scheduler/config?"):
        parsed, body = _page(client, src=source)
        assert "系统使用说明" in "".join(parsed.text)
        assert len("".join(parsed.text)) >= 100
        _source_visible(parsed, raw)
        assert _link(parsed, "返回刚才页面") == source
        assert "相关说明" not in [text for _href, text in parsed.links]
        assert "page=" not in _link(parsed, "下载说明书原文")

    for endpoint, title, default_return in (
        ("material.materials_page", "物料主数据", "返回首页"),
        ("scheduler.config_page", "高级设置", "返回排产首页"),
        ("dashboard.index", "第一次使用路线图", "返回首页"),
    ):
        parsed, _body = _page(client, page=endpoint)
        assert "本页说明 - " + title in "".join(parsed.text)
        assert _link(parsed, default_return) == ("/scheduler/" if endpoint.startswith("scheduler.") else "/")
        _source_visible(parsed, manuals.build_page_fallback_text(endpoint))
        full_links = [href for href, _label in parsed.links if urlsplit(href).fragment and not href.startswith("#")]
        assert full_links
        for href in full_links:
            full, _ = _page(client, **{key: values[0] for key, values in parse_qs(urlsplit(href).query).items()})
            assert urlsplit(href).fragment in full.ids

    parsed, _ = _page(client, page="dashboard.index", src="/?")
    for text in ("先准备资料", "先模拟，再正式排产", "排完去哪里看", "不在这里导出或恢复版本", "当前页只展示前 5 条"):
        assert text in "".join(parsed.text)

    for unsafe in ("http://evil.example/x", "//evil.example/x"):
        parsed, body = _page(client, page="material.materials_page", src=unsafe)
        assert _link(parsed, "返回首页") == "/"
        assert "evil.example" not in body
        assert "page=material.materials_page" in _link(parsed, "下载整本说明书")
        assert all("src=" not in href for href, _label in parsed.links)

    invalid, body = _page(client, page="unknown.endpoint", src="/material/materials?")
    assert "系统使用说明" in "".join(invalid.text)
    assert "本页说明 -" not in body
    assert "unknown.endpoint" not in _link(invalid, "下载说明书原文")
    _source_visible(invalid, raw)
    download = client.get("/scheduler/config/manual/download", query_string={"page": "material.materials_page", "src": "/material/materials?"})
    assert download.status_code == 200
    assert quote("系统使用说明.md", safe="") in download.headers["Content-Disposition"]
    assert download.data == (REPO_ROOT / "static/docs/scheduler_manual.md").read_bytes()

    with patch("web.routes.domains.scheduler.scheduler_config._resolve_scheduler_manual_md_path", return_value=(None, [])):
        response = client.get("/scheduler/config/manual/download", query_string={"page": "unknown.endpoint", "src": "http://evil.example/x"})
    assert response.status_code in (302, 303)
    assert "evil.example" not in response.headers["Location"] and "unknown.endpoint" not in response.headers["Location"]
    assert _business_state(client) == before


def test_manual_entry_scope_contract(monkeypatch) -> None:
    main(monkeypatch)


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__]))
