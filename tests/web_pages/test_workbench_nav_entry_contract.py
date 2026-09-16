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
    ("dashboard", "值班台"), ("process", "基础资料"), ("basedata", "资料总览"),
    ("batches", "批次管理"), ("run", "执行排产"), ("analysis", "选择排产方案"),
    ("trial", "试调排产方案"), ("field", "现场记录"), ("fieldgantt", "现场实际甘特"),
    ("reports", "报表中心"), ("calib", "工时定额校准"), ("system", "系统管理"),
]
SUPPORTED_VIEWS = {"dashboard", "process", "batches", "run", "analysis", "gantt", "delay", "field",
                   "fieldgantt", "review", "reports", "calib", "basedata", "system", "trial"}
ALIASES = {"gantt": "analysis", "delay": "analysis", "review": "reports"}


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
    assert "boot.nav_groups.map" in source and "group.items.map" in source
    assert "{item.label}" in source and "href={href(item.id)}" in source
    assert source.count("<window.WorkbenchCaption.Caption />") == 1
    assert "const NAV_GROUPS" not in source
    # The plan-center tab strip hides inside 排产历史 and help carries the current view back to the manual.
    assert "WorkbenchNavigation.historyView(page)" in source and "WorkbenchNavigation.helpUrl(boot, page)" in source
    assert not (REPO_ROOT / "templates/base.html").exists()


def test_default_ui_serves_plan_workbench_menu(app_client) -> None:
    boot = canonical_boot(app_client, "/", "dashboard", {})
    assert {key for key, _ in DESTINATIONS} <= set(boot["enabled_views"])
    parser = _WorkbenchMenuParser()
    parser.feed(_menu(app_client.application))
    assert any(text == "值班台" and href == "/workbench?view=dashboard" for href, text in parser.links)


def test_workbench_menu_renders_approved_groups_without_losing_hidden_views(db_env) -> None:
    app = importlib.import_module("app").create_app()
    boot = boot_payload(app.test_client().get("/workbench"))
    parser = _WorkbenchMenuParser()
    parser.feed(_menu(app))
    items = [item for group in boot["nav_groups"] for item in group["items"]]
    expected = [("/workbench/trial" if item["id"] == "trial" else "/workbench?view=" + item["id"], item["label"])
                for item in items]
    assert parser.links == expected
    assert len(parser.links) == 12
    assert [(item["id"], item["label"]) for item in items] == DESTINATIONS
    assert set(boot["enabled_views"]) == set(boot["titles"]) == SUPPORTED_VIEWS
    assert boot["view_aliases"] == ALIASES


def test_navigation_metadata_preserves_supported_view_contract_and_help(app_client) -> None:
    from web.routes.workbench.navigation_boot import SUPPORTED_VIEWS as ROUTE_VIEWS

    boot = boot_payload(app_client.get("/workbench"))
    assert set(boot["enabled_views"]) == set(VIEW_TITLES) == set(ROUTE_VIEWS) == SUPPORTED_VIEWS
    assert [group["title"] for group in boot["nav_groups"]] == ["值班台", "数据准备", "排产", "现场", "统计分析", "系统"]
    assert [(item["id"], item["label"]) for group in boot["nav_groups"] for item in group["items"]] == DESTINATIONS
    assert boot["view_aliases"] == ALIASES
    for group in boot["nav_groups"]:
        assert len({item["icon"] for item in group["items"]}) == len(group["items"])
    assert boot["help_url"] == "/scheduler/config/manual"
    manual = app_client.get(boot["help_url"])
    assert manual.status_code == 200 and 'aria-label="说明书正文"' in manual.get_data(as_text=True)
    # The shell appends the current view as src so the manual renders a way back into the workbench.
    manual = app_client.get(boot["help_url"], query_string={"src": "/workbench?view=analysis"})
    assert manual.status_code == 200 and 'href="/workbench?view=analysis">返回刚才页面</a>' in manual.get_data(as_text=True)


@pytest.mark.parametrize("view", sorted(SUPPORTED_VIEWS))
def test_each_supported_view_stays_directly_reachable(app_client, view) -> None:
    path = "/workbench/trial" if view == "trial" else "/workbench?view=" + view
    boot = boot_payload(app_client.get(path))
    assert boot["view"] == view
    assert boot["view_aliases"] == ALIASES


@pytest.mark.parametrize("view", sorted(ALIASES))
def test_hidden_view_urls_keep_explicit_identity_and_context(app_client, view) -> None:
    context = {"scope": {"plan_ref": "a" * 48}} if view == "review" else {"plan_ref": "a" * 48}
    navigation = {"version": 1, "view": view, "context": context}
    query = {"view": view, "nav": json.dumps(navigation)}
    for _ in range(2):
        boot = boot_payload(app_client.get("/workbench", query_string=query))
        assert boot["view"] == view and boot["navigation"] == navigation


def test_workbench_header_controls_show_instance_help_and_preference_actions(app_client) -> None:
    app_client.application.config["WORKBENCH_INSTANCE_LABEL"] = "导航合同测试副本"
    result = browser_contract("""
const controls = document.querySelector('.header-controls');
expect(controls.querySelector('.wb-instance-label').textContent === '导航合同测试副本');
expect(/^\\/scheduler\\/config\\/manual\\?src=%2Fworkbench%3Fview%3D[a-z]+$/.test(controls.querySelector('a.wb-help-link').getAttribute('href')),
  'help link must carry the current view as src');
const theme = Array.from(controls.querySelectorAll('button')).find(button => /切换[深浅]色/.test(button.textContent));
const density = Array.from(controls.querySelectorAll('button')).find(button => button.textContent === '紧凑表格');
expect(theme && density, 'Missing preference action');
const before = document.documentElement.dataset.theme;
theme.click(); await new Promise(resolve => setTimeout(resolve, 30));
expect(document.documentElement.dataset.theme !== before, 'Theme action did not change theme');
expect(theme.textContent.includes(document.documentElement.dataset.theme === 'dark' ? '切换浅色' : '切换深色'));
const denseBefore = density.getAttribute('aria-pressed');
density.click(); await new Promise(resolve => setTimeout(resolve, 30));
expect(density.getAttribute('aria-pressed') !== denseBefore, 'Density action did not change preference');
expect(document.documentElement.dataset.density === (density.getAttribute('aria-pressed') === 'true' ? 'compact' : 'comfortable'));
return {theme: document.documentElement.dataset.theme, density: document.documentElement.dataset.density};
""", app=app_client.application)
    assert result["theme"] in ("dark", "light") and result["density"] in ("compact", "comfortable")


def test_shell_plan_tabs_preserve_explicit_context_and_alias_highlight(app_client) -> None:
    context = {"plan_ref": "a" * 48, "range_start": "2026-05-06T00:00:00", "range_end": "2026-05-08T00:00:00"}
    navigation = {"version": 1, "view": "gantt", "context": context}
    path = "/workbench?" + urlencode({"view": "gantt", "nav": json.dumps(navigation)})
    result = browser_contract("""
const initial = JSON.parse(document.getElementById('workbench-boot').textContent), N = window.WorkbenchNavigation;
expect(document.querySelector('.sidebar-nav [aria-current="page"]').getAttribute('href') === '/workbench?view=analysis');
expect(document.querySelector('#wb-view-tab-gantt').getAttribute('aria-selected') === 'true');
const currentTab = document.querySelector('#wb-view-tab-gantt'); currentTab.focus();
const backShortcut = new KeyboardEvent('keydown', {key: 'ArrowLeft', altKey: true, bubbles: true, cancelable: true});
expect(currentTab.dispatchEvent(backShortcut), 'Tabs swallowed the browser back shortcut');
expect(!currentTab.dispatchEvent(new KeyboardEvent('keydown', {key: 'ArrowLeft', bubbles: true, cancelable: true})));
expect(document.activeElement.id === 'wb-view-tab-analysis', 'Plain arrow did not move tab focus');
expect(N.read(initial).view === 'gantt', 'Moving tab focus changed the current scope');
const tab = document.querySelector('#wb-view-tab-delay'); tab.click();
for (let i = 0; i < 100 && new URL(location.href).searchParams.get('view') !== 'delay'; i++) await new Promise(resolve => setTimeout(resolve, 10));
const page = N.read(initial);
expect(page.view === 'delay' && page.context.plan_ref === initial.navigation.context.plan_ref);
expect(page.context.range_start === initial.navigation.context.range_start && page.context.range_end === initial.navigation.context.range_end);
expect(document.querySelector('#wb-view-tab-delay').getAttribute('aria-selected') === 'true');
return {view: page.view, context: page.context};
""", app=app_client.application, path=path)
    assert result["view"] == "delay"
    assert all(result["context"][key] == value for key, value in context.items())


def test_shell_history_guard_retains_real_batch_draft_until_leave_is_confirmed(app_client) -> None:
    result = browser_contract("""
const wait = async predicate => { for (let i = 0; i < 300; i++) { if (predicate()) return; await new Promise(resolve => setTimeout(resolve, 10)); } throw new Error('Real batch draft transition timed out'); };
const button = name => Array.from(document.querySelectorAll('button')).find(node => node.textContent.trim() === name);
document.querySelector('.sidebar-nav a[href="/workbench?view=batches"]').click();
await wait(() => button('新增批次') && !button('新增批次').disabled);
button('新增批次').click();
await wait(() => document.querySelector('input[aria-label="批次号"]'));
const field = document.querySelector('input[aria-label="批次号"]');
Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(field, '保留批次草稿');
field.dispatchEvent(new Event('input', {bubbles: true}));
await wait(() => window.WorkbenchGuards.hasDirty());
const url = location.href;
history.back(); await wait(() => button('留在当前页面') && location.href === url);
expect(field.isConnected && field.value === '保留批次草稿', 'Editor was discarded before approval');
button('留在当前页面').click(); await wait(() => !button('留在当前页面'));
expect(location.href === url && field.isConnected && field.value === '保留批次草稿');
history.back(); await wait(() => button('放弃未保存内容并继续') && location.href === url);
button('放弃未保存内容并继续').click();
await wait(() => !field.isConnected && !window.WorkbenchGuards.hasDirty());
expect(new URL(location.href).searchParams.get('view') !== 'batches', 'Approved history navigation did not finish');
expect(document.querySelector('.sidebar-nav [aria-current="page"]').getAttribute('href') === '/workbench?view=dashboard');
return {draftPreservedUntilApproval: true, finalView: 'dashboard'};
""", app=app_client.application)
    assert result == {"draftPreservedUntilApproval": True, "finalView": "dashboard"}


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
        message = "没有丢掉" if view in ("dashboard", "analysis", "gantt") else "没有恢复上次选择"
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
                with pytest.raises(WorkbenchCommandRejected, match="只看当前正式计划") as failure:
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
        assert not name.startswith("on") and (name == "data-wb-icon" or not name.startswith("data-"))
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
