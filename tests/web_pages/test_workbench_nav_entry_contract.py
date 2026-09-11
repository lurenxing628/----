"""React sidebar and typed navigation preserve scope, identity and read-only entries."""

from __future__ import annotations

import importlib
import json
from contextlib import closing
from html.parser import HTMLParser
from unittest.mock import patch
from urllib.parse import urlencode

import pytest

from core.infrastructure.database import get_connection
from core.models.workbench_command import WorkbenchCommandRejected
from core.models.workbench_plan_reference import WorkbenchPlanLocator
from core.models.workbench_report import ReportScope
from core.services.workbench.report_facts import WorkbenchReportFacts
from tests._support.paths import REPO_ROOT
from tests._support.workbench_browser_contract import browser_contract
from tests._support.workbench_web_contract import boot_payload, canonical_boot
from web.routes.workbench.pages import VIEW_TITLES

NAV_INPUTS = ("static/workbench/app/WorkbenchNavigation.js",)
DESTINATIONS = [
    ("process", "基础资料"), ("batches", "批次管理"), ("run", "执行排产"),
    ("analysis", "选择排产方案"), ("trial", "方案试调"), ("gantt", "设备 / 人员 / 批次甘特"),
    ("field", "现场记录"), ("fieldgantt", "现场实际甘特"), ("review", "执行复盘"),
    ("reports", "报表中心"), ("calib", "工时定额校准"), ("dashboard", "值班台"),
    ("basedata", "主数据总览"), ("system", "系统管理"),
]


class _WorkbenchMenuParser(HTMLParser):
    """Inspect only the real sidebar, not invisible boot fields or application code."""

    def __init__(self):
        super().__init__()
        self.links, self.tags, self.attrs = [], [], []
        self._link = None

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs.extend((tag, key, value or "") for key, value in attrs)
        if tag == "a":
            self._link = [dict(attrs).get("href"), []]

    def handle_data(self, text):
        if self._link is not None:
            self._link[1].append(text)

    def handle_endtag(self, tag):
        if tag == "a" and self._link is not None:
            self.links.append((self._link[0], " ".join("".join(self._link[1]).split())))
            self._link = None


def _menu(app):
    """Read the actual React navigation without invoking any command."""
    return browser_contract(
        "const menu = document.querySelector('.sidebar-nav'); expect(menu); return menu.outerHTML;",
        app=app,
    )


def _read(name):
    """Read the current declared presentation source."""
    return (REPO_ROOT / name).read_text(encoding="utf-8")


def test_base_header_mounts_plan_workbench_menu() -> None:
    source = _read("frontend/workbench/app/main.jsx")
    assert '<nav className="sidebar-nav">' in source
    assert "NAV_GROUPS.map" in source and "group.items.map" in source
    assert "{item.label}" in source and "href={href(item.id)}" in source
    assert source.count("<window.WorkbenchCaption.Caption />") == 1
    assert "const NAV_GROUPS" not in source
    assert not (REPO_ROOT / "templates/base.html").exists()


def test_default_ui_serves_plan_workbench_menu(app_client) -> None:
    boot = canonical_boot(app_client, "/", "dashboard", {})
    assert {key for key, _ in DESTINATIONS} <= set(boot["enabled_views"])
    parser = _WorkbenchMenuParser()
    parser.feed(_menu(app_client.application))
    assert any(text == "值班台" and href == "/workbench?view=dashboard" for href, text in parser.links)


def test_workbench_menu_renders_six_core_destinations(db_env) -> None:
    app = importlib.import_module("app").create_app()
    parser = _WorkbenchMenuParser()
    parser.feed(_menu(app))
    expected = [("/workbench/trial" if key == "trial" else "/workbench?view=" + key, label)
                for key, label in DESTINATIONS]
    assert parser.links == expected
    assert len(parser.links) == 14
    assert {"dashboard", "reports", "analysis", "gantt", "field", "review"} <= {key for key, _ in DESTINATIONS}


def test_workbench_menu_preserves_report_workbench_context(db_env) -> None:
    app = importlib.import_module("app").create_app()
    context = {"scope": {"source": "production", "plan_ref": "a" * 48,
                         "plan_finish_date_from": "2026-05-06", "plan_finish_date_to": "2026-05-07",
                         "batch_ref": "b" * 48, "resource_type": "machine", "resource_ref": "c" * 48}}
    navigation = {"version": 1, "view": "reports", "context": context}
    query = urlencode({"view": "reports", "nav": json.dumps(navigation)})
    boot = boot_payload(app.test_client().get("/workbench?" + query))
    assert boot["navigation"] == navigation
    observed = browser_contract("""
const boot = data.boot;
history.replaceState(null, '', '/workbench?view=reports&nav=' + encodeURIComponent(JSON.stringify(boot.navigation)));
const N = window.WorkbenchNavigation, first = N.read(boot);
expect(JSON.stringify(first.context) === JSON.stringify(boot.navigation.context), 'URL scope changed');
const ganttContext = {plan_ref: first.context.scope.plan_ref, range_start:'2026-05-06T00:00:00', range_end:'2026-05-08T00:00:00'};
const gantt = N.navigate(boot, first, 'gantt', ganttContext);
expect(JSON.stringify(gantt.context) === JSON.stringify(ganttContext), 'Explicit target changed');
const back = N.navigate(boot, gantt, 'reports');
expect(JSON.stringify(back.context) === JSON.stringify(first.context), 'Returning discarded original filters');
return {original: first.context, returned: back.context, target: gantt.context};
""", scripts=NAV_INPUTS, data={"boot": boot})
    assert observed["original"] == observed["returned"] == context
    assert observed["target"]["plan_ref"] == context["scope"]["plan_ref"]


def test_workbench_menu_disables_team_context_links_that_would_400(db_env) -> None:
    app = importlib.import_module("app").create_app()
    client = app.test_client()
    for view in ("dashboard", "reports", "analysis", "review", "gantt"):
        context = {"scope": {"plan_ref": "a" * 48, "resource_type": "team", "resource_ref": "b" * 48}}
        if view in ("gantt", "analysis"):
            context = {"plan_ref": "a" * 48, "resource_type": "team", "resource_ref": "b" * 48}
        navigation = {"version": 1, "view": view, "context": context}
        response = client.get("/workbench", query_string={"view": view, "nav": json.dumps(navigation)})
        assert response.status_code == 400
        assert "Location" not in response.headers
        message = "未忽略" if view in ("dashboard", "analysis", "gantt") else "未恢复旧选择"
        assert message in response.get_data(as_text=True)
        assert 'id="workbench-boot"' not in response.get_data(as_text=True)
    # Team-specific dispatch has no equivalent typed navigation; never silently widen it.
    response = client.get("/workbench", query_string={"view": "field", "nav": json.dumps(
        {"version": 1, "view": "field", "context": {"scope_type": "team", "team_id": "T-RPT"}})})
    assert response.status_code == 400 and "Location" not in response.headers


def test_workbench_menu_disables_execution_review_for_non_formal_context(db_env) -> None:
    with closing(get_connection(db_env)) as conn:
        reader = WorkbenchReportFacts(conn)
        for locator in (WorkbenchPlanLocator(12, "baseline_best", "SCN-1"), WorkbenchPlanLocator(12, "adopted", "SCN-1")):
            with patch.object(reader.plans.references, "resolve_plan", return_value=locator) as resolve, \
                    patch.object(reader.plans, "_selected") as selected, patch.object(reader.engine, "latest_version") as latest:
                with pytest.raises(WorkbenchCommandRejected, match="不能使用候选或模拟方案") as failure:
                    reader.current_plan(ReportScope(plan_ref="a" * 48))
                assert failure.value.code == "plan_not_current_official"
                resolve.assert_called_once_with("a" * 48)
                selected.assert_not_called()
                latest.assert_not_called()


def test_workbench_menu_is_readonly_and_hides_internal_fields(db_env) -> None:
    app = importlib.import_module("app").create_app()
    html = _menu(app)
    parser = _WorkbenchMenuParser()
    parser.feed(html)
    for fragment in ("plan_role", "scenario_id", "source_table", "candidate_id", "op_id", "schedule_id",
                     "actual-template", "actual-import", "actual-write", "formaction=", "javascript:",
                     "data-actual-record-url-template", "导入", "模板下载"):
        assert fragment.lower() not in html.lower()
    assert {"base", "button", "embed", "form", "iframe", "input", "link", "object",
            "script", "select", "style", "textarea"}.isdisjoint(parser.tags)
    expected = {"/workbench/trial" if key == "trial" else "/workbench?view=" + key for key, _ in DESTINATIONS}
    for tag, name, value in parser.attrs:
        assert not name.startswith("on") and not name.startswith("data-")
        assert name not in {"download", "method", "formaction"}
        assert "javascript:" not in value.lower()
        if tag == "a" and name == "href":
            assert value in expected


def test_workbench_menu_uses_local_css_and_no_javascript_dependency() -> None:
    # React replaces the JS-free macro; both its scripts and CSS must be local and prebuilt.
    from web.routes.workbench.assets import read_asset_manifest

    manifest = read_asset_manifest(str(REPO_ROOT / "static"))
    assert manifest["target"] == "chrome109"
    assert "workbench/app/main.js" in manifest["scripts"]
    assert "workbench/app/WorkbenchNavigation.js" in manifest["scripts"]
    assert "workbench/prototype/ui_kits/workbench/index.inline.css" in manifest["styles"]
    for name in manifest["scripts"] + manifest["styles"] + [manifest["theme_script"]]:
        assert (REPO_ROOT / "static" / name).is_file()
        assert not any(fragment in name for fragment in ("https://", "http://", "cdn", "unpkg"))
    host = _read("templates/workbench/index.html")
    assert "<noscript>" in host and "JavaScript" in host
    assert "text/babel" not in host
    assert "aps-workbench-ready" in host and "role', 'alert'" in host
