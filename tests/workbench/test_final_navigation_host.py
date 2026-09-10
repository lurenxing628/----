"""Real factory HTML binding for navigation; domain readers still resolve identities."""

import json
import sqlite3
from html.parser import HTMLParser

import pytest

from tests.workbench.final_navigation_support import REF, VALID_CONTEXTS, nav_args
from web.routes.workbench.pages import VIEW_TITLES


class BootParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.inside = False
        self.chunks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("id") == "workbench-boot":
            self.inside = True

    def handle_endtag(self, tag):
        if tag == "script":
            self.inside = False

    def handle_data(self, data):
        if self.inside:
            self.chunks.append(data)


def boot(response):
    parser = BootParser()
    parser.feed(response.get_data(as_text=True))
    return json.loads("".join(parser.chunks))


@pytest.fixture
def navigation_client(app_client, tmp_path, monkeypatch):
    root = tmp_path / "navigation-static"
    folder = root / "workbench"
    folder.mkdir(parents=True)
    for name in ("theme.js", "entry.js", "style.css"):
        (folder / name).write_text("/* HTML contract fixture, not a browser build. */", encoding="utf-8")
    manifest = {"schema_version": 1, "target": "chrome109", "styles": ["workbench/style.css"],
                "scripts": ["workbench/entry.js"], "theme_script": "workbench/theme.js", "files": []}
    (folder / "asset-manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setattr(app_client.application, "static_folder", str(root))
    return app_client


def test_valid_html_context_is_exact_and_no_identity_or_audit_is_written(navigation_client):
    conn = sqlite3.connect(navigation_client.application.config["DATABASE_PATH"])
    try:
        before = list(conn.iterdump())
        for view, context in VALID_CONTEXTS:
            endpoint = "/workbench/trial" if view == "trial" else "/workbench"
            response = navigation_client.get(endpoint, query_string=nav_args(view, context))
            assert response.status_code == 200, response.get_data(as_text=True)
            result = boot(response)
            assert result["view"] == view
            assert result["navigation"] == {"version": 1, "view": view, "context": context}
            assert response.headers["Cache-Control"] == "no-store"
        assert list(conn.iterdump()) == before
    finally:
        conn.close()


def test_unselected_pages_have_no_invented_navigation(navigation_client):
    for view in VIEW_TITLES:
        response = navigation_client.get("/workbench", query_string={"view": view})
        assert response.status_code == 200
        assert boot(response)["navigation"] is None


@pytest.mark.parametrize("query", [
    [("view", "gantt"), ("view", "analysis")],
    [("view", "gantt"), ("version", "7")],
    [("view", "gantt"), ("plan_role", "adopted")],
    [("view", "gantt"), ("nav", "{")],
    [("view", "gantt"), ("nav", "null"), ("nav", "null")],
    [("view", "gantt"), ("nav", '{"version":1,"view":"gantt","context":{"plan_ref":"bad"}}')],
])
def test_invalid_navigation_is_rejected_before_reading_assets(navigation_client, monkeypatch, query):
    def unexpected(_folder):
        raise AssertionError("Invalid navigation must be rejected before loading a manifest")

    monkeypatch.setattr("web.routes.workbench.pages.read_asset_manifest", unexpected)
    response = navigation_client.get("/workbench", query_string=query)
    assert response.status_code == 400
    text = response.get_data(as_text=True)
    assert 'role="alert"' in text and 'aria-label="恢复入口"' in text
    assert 'id="workbench-boot"' not in text
    assert response.headers["Cache-Control"] == "no-store"


def test_trial_path_cannot_accept_another_view_without_nav(navigation_client):
    response = navigation_client.get("/workbench/trial?view=reports")
    assert response.status_code == 400
    assert 'id="workbench-boot"' not in response.get_data(as_text=True)


def test_html_boot_escapes_script_end_without_changing_query(navigation_client):
    query = '</script><img src=x onerror="invalid">'
    context = {"scope": {"plan_ref": REF, "query": query}}
    response = navigation_client.get("/workbench", query_string=nav_args("reports", context))
    assert response.status_code == 200
    assert boot(response)["navigation"]["context"] == context
    assert "<img src=x" not in response.get_data(as_text=True)


def test_unknown_view_and_missing_assets_keep_no_store(navigation_client, tmp_path, monkeypatch):
    response = navigation_client.get("/workbench?view=unknown")
    assert response.status_code == 404 and response.headers["Cache-Control"] == "no-store"
    monkeypatch.setattr(navigation_client.application, "static_folder", str(tmp_path / "missing"))
    response = navigation_client.get("/workbench?view=system")
    assert response.status_code == 503 and response.headers["Cache-Control"] == "no-store"
    assert 'aria-label="恢复入口"' in response.get_data(as_text=True)


def test_old_form_messages_reach_boot_once_without_html_execution(navigation_client):
    messages = [("success", "原表单已保存"), ("warning", "<script>notExecutable()</script>")]
    with navigation_client.session_transaction() as session:
        session["_flashes"] = messages
    response = navigation_client.get("/workbench?view=process")
    assert response.status_code == 200
    assert boot(response)["messages"] == [{"category": category, "message": message} for category, message in messages]
    assert "<script>notExecutable()" not in response.get_data(as_text=True)
    assert boot(navigation_client.get("/workbench?view=process"))["messages"] == []


def test_unavailable_page_preserves_visible_form_result_before_recovery(navigation_client):
    with navigation_client.session_transaction() as session:
        session["_flashes"] = [("success", "原操作已提交，请勿重复提交。")]
    response = navigation_client.get("/workbench?view=gantt&nav={")
    assert response.status_code == 400
    text = response.get_data(as_text=True)
    assert 'aria-label="操作结果"' in text and "原操作已提交，请勿重复提交。" in text
    assert boot(navigation_client.get("/workbench?view=system"))["messages"] == []
