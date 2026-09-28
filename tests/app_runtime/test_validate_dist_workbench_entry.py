"""Frozen delivery checks must follow the current workbench and retired URLs."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

import pytest
from flask import Flask, render_template

import validate_dist_exe as validator
from tests._support.paths import REPO_ROOT

BASE = "http://localhost"


@pytest.fixture
def workbench_html():
    manifest = json.loads((REPO_ROOT / "static/workbench/asset-manifest.json").read_text(encoding="utf-8"))
    app = Flask(__name__, template_folder=str(REPO_ROOT / "templates"), static_folder=str(REPO_ROOT / "static"))
    boot = {"schema_version": 1, "view": "dashboard", "enabled_views": ["dashboard"], "titles": {"dashboard": "APS"}}
    with app.test_request_context("/workbench"):
        return render_template("workbench/index.html", assets=manifest, boot=boot)


def _page(monkeypatch, body, status=200, final_url=BASE + "/workbench"):
    monkeypatch.setattr(validator, "_http_get_page", lambda _url: (status, body, final_url))


def test_real_template_has_current_workbench_boot_and_local_assets(workbench_html, monkeypatch):
    _page(monkeypatch, workbench_html)
    validator._assert_workbench_page(BASE, "/workbench", "dashboard")


def test_asset_version_query_does_not_change_local_payload_identity(workbench_html, monkeypatch):
    for anchor in validator._STATIC_BUNDLE_ANCHORS:
        workbench_html = workbench_html.replace("/" + anchor + '"', "/" + anchor + '?v=0123456789abcdef"')
    _page(monkeypatch, workbench_html)
    validator._assert_workbench_page(BASE, "/workbench", "dashboard")


@pytest.mark.parametrize("status", [404, 410, 500, 503])
def test_workbench_error_status_never_passes_even_with_valid_html(workbench_html, monkeypatch, status):
    _page(monkeypatch, workbench_html, status=status)
    with pytest.raises(RuntimeError, match="入口响应"):
        validator._assert_workbench_page(BASE, "/workbench", "dashboard")


@pytest.mark.parametrize("before,after", [
    ('id="root"', 'id="missing-root"'),
    ('class="aps-workbench"', 'class="another-page"'),
    ('id="workbench-boot"', 'id="missing-boot"'),
    ('type="application/json"', 'type="text/plain"'),
    ('"schema_version": 1', '"schema_version": 2'),
    ('"view": "dashboard"', '"view": "system"'),
    ('"enabled_views": ["dashboard"]', '"enabled_views": "dashboard"'),
    ('<div id="root"', '<div id="root"></div><div id="root"'),
])
def test_malformed_or_wrong_workbench_is_rejected(workbench_html, monkeypatch, before, after):
    assert before in workbench_html
    _page(monkeypatch, workbench_html.replace(before, after))
    with pytest.raises(RuntimeError):
        validator._assert_workbench_page(BASE, "/workbench", "dashboard")


@pytest.mark.parametrize("anchor", validator._STATIC_BUNDLE_ANCHORS)
def test_unreferenced_required_script_or_stylesheet_is_rejected(workbench_html, monkeypatch, anchor):
    assert "/" + anchor in workbench_html
    _page(monkeypatch, workbench_html.replace("/" + anchor, "/static/workbench/missing"))
    with pytest.raises(RuntimeError, match="关键脚本或样式"):
        validator._assert_workbench_page(BASE, "/workbench", "dashboard")


def test_external_script_reference_is_rejected(workbench_html, monkeypatch):
    _page(monkeypatch, workbench_html.replace('src="/static/workbench/app/main.js"', 'src="https://outside.invalid/app.js"'))
    with pytest.raises(RuntimeError, match="非本机交付资源"):
        validator._assert_workbench_page(BASE, "/workbench", "dashboard")


@pytest.mark.parametrize("target", ["http://elsewhere.invalid/workbench", BASE + "/error"])
def test_redirect_to_wrong_origin_or_non_workbench_page_is_rejected(workbench_html, monkeypatch, target):
    _page(monkeypatch, workbench_html, final_url=target)
    with pytest.raises(RuntimeError, match="入口响应"):
        validator._assert_workbench_page(BASE, "/", "dashboard")


@pytest.mark.parametrize("status", [200, 404, 500])
def test_retired_endpoint_requires_410(monkeypatch, status):
    body = '<main data-workbench-legacy-response="true">旧入口已退役 原业务数据、保存的配置和历史记录仍保留</main>'
    _page(monkeypatch, body, status=status, final_url=BASE + "/personnel/")
    with pytest.raises(RuntimeError, match="410 退役页"):
        validator._assert_retired_page(BASE, "/personnel/")


def test_generic_410_is_not_a_retirement_page(monkeypatch):
    _page(monkeypatch, "Gone", status=410, final_url=BASE + "/personnel/")
    with pytest.raises(RuntimeError, match="410 退役页"):
        validator._assert_retired_page(BASE, "/personnel/")


def test_checks_match_real_registered_entry_and_retirement_routes(app_client, monkeypatch):
    from web.routes.workbench.navigation_metadata import VIEW_TITLES

    def fetch(url):
        parts = urlsplit(url)
        path = parts.path + ("?" + parts.query if parts.query else "")
        response = app_client.get(path, follow_redirects=True)
        return response.status_code, response.get_data(as_text=True), response.request.url

    assert set(validator._WORKBENCH_VIEWS) == set(VIEW_TITLES)
    monkeypatch.setattr(validator, "_http_get_page", fetch)
    validator._assert_workbench_page(BASE, "/", "dashboard")
    validator._assert_workbench_page(BASE, "/workbench", "dashboard")
    for view in validator._WORKBENCH_VIEWS:
        validator._assert_workbench_page(BASE, "/workbench?view=" + view, view)
    validator._assert_workbench_page(BASE, "/workbench/trial", "trial")
    for path in validator._RETIRED_PAGE_PATHS:
        validator._assert_retired_page(BASE, path)


def test_http_reader_keeps_error_body_and_final_redirect_target():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/":
                self.send_response(302)
                self.send_header("Location", "/workbench")
                self.end_headers()
                return
            self.send_response(410 if self.path == "/old" else 200)
            self.end_headers()
            self.wfile.write(b"retired" if self.path == "/old" else b"workbench")

        def log_message(self, _format, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = "http://127.0.0.1:" + str(server.server_port)
    try:
        assert validator._http_get_page(origin + "/") == (200, "workbench", origin + "/workbench")
        assert validator._http_get_page(origin + "/old") == (410, "retired", origin + "/old")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
