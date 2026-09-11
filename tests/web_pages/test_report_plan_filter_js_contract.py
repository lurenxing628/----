"""Retired form filters are replaced by explicit identity-bound navigation state."""

from __future__ import annotations

import json
import os
import subprocess

from tests._support.paths import REPO_ROOT


def test_report_plan_filter_restores_scenario_when_identity_returns_to_initial() -> None:
    assert not (REPO_ROOT / "static/js/report_plan_filter.js").exists()
    source = (REPO_ROOT / "frontend/workbench/app/WorkbenchNavigation.js").read_text(encoding="utf-8")
    harness = r"""
const assert = require('assert');
const first = {scope: {plan_ref: 'a'.repeat(48), batch_ref: 'b'.repeat(48),
  resource_type: 'machine', resource_ref: 'c'.repeat(48),
  plan_finish_date_from: '2026-05-06', plan_finish_date_to: '2026-05-06'}};
const changedVersion = {scope: {plan_ref: 'd'.repeat(48)}};
const changedRole = {scope: {plan_ref: 'e'.repeat(48)}};
const nav = {version: 1, view: 'reports', context: first};
const boot = {entry_url: '/workbench', trial_url: '/workbench/trial',
  titles: {reports: '报表', analysis: '分析', review: '复盘'}, navigation: nav};
global.window = {scrollX: 0, scrollY: 0};
global.document = {querySelector: () => null};
global.location = new URL('http://localhost/workbench?view=reports&nav=' + encodeURIComponent(JSON.stringify(nav)));
global.history = {state: null,
  replaceState(value, unused, url) { this.state = value; global.location = new URL(url, location); },
  pushState(value, unused, url) { this.state = value; global.location = new URL(url, location); }};
eval(process.env.REPORT_PLAN_FILTER_SOURCE);
const api = window.WorkbenchNavigation;
let page = api.read(boot);
assert.deepStrictEqual(page.context, first);
page = api.navigate(boot, page, 'reports', changedVersion);
assert.deepStrictEqual(api.read(boot).context, changedVersion);
assert.strictEqual(page.context.scope.batch_ref, undefined);
assert.strictEqual(page.context.scope.resource_ref, undefined);
page = api.navigate(boot, page, 'reports', changedRole);
assert.deepStrictEqual(api.read(boot).context, changedRole);
assert.notStrictEqual(page.context.scope.plan_ref, first.scope.plan_ref);
page = api.navigate(boot, page, 'analysis', {plan_ref: changedRole.scope.plan_ref});
page = api.navigate(boot, page, 'reports');
assert.deepStrictEqual(page.context, changedRole);
page = api.navigate(boot, page, 'reports', first);
assert.deepStrictEqual(api.read(boot).context, first);
page = api.navigate(boot, page, 'analysis', {plan_ref: first.scope.plan_ref});
page = api.navigate(boot, page, 'reports');
assert.deepStrictEqual(page.context, first);
api.replaceContext(boot, page, changedRole);
assert.deepStrictEqual(api.read(boot).context, changedRole);
page = api.read(boot);
page = api.navigate(boot, page, 'reports', {});
assert.deepStrictEqual(api.read(boot).context, {});
const wrong = {version: 1, view: 'reports', context: changedVersion};
global.location = new URL('http://localhost/workbench?view=reports&nav=' + encodeURIComponent(JSON.stringify(wrong)));
assert.throws(() => api.read(boot), /未自动切换对象或扩大范围/);
assert(!JSON.stringify(first).includes('scenario_id'));
assert(!JSON.stringify(first).includes('plan_context_token'));
console.log(JSON.stringify({restored: first, changed: changedRole, rejectedMismatch: true}));
"""
    result = subprocess.run(
        ["node", "-e", harness], cwd=str(REPO_ROOT),
        env={**os.environ, "REPORT_PLAN_FILTER_SOURCE": source},
        text=True, capture_output=True, check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["restored"]["scope"]["plan_ref"] == "a" * 48
    assert payload["changed"]["scope"] == {"plan_ref": "e" * 48}
    assert payload["rejectedMismatch"] is True
