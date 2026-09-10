'use strict';
const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), assert = require('node:assert/strict');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const host = { window: { ResourceControls: { Button() {}, ErrorBox() {}, Issues() {} } },
  React: { createElement(type, props, ...children) { return { type, props: { ...props, children } }; } },
  URLSearchParams, AbortController, setTimeout, clearTimeout };
for (const file of ['PointContract.js', 'RunCandidateAPI.js', 'RunBaselineAPI.js', 'DashboardContract.js', 'DashboardAnalysisAPI.js',
  'DashboardCandidateComparisonAPI.js', 'DashboardSession.js', 'SystemMaintenanceAPI.js']) {
  vm.runInNewContext(fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8'), host, { filename: file });
}
const sources = ['DashboardPanels.jsx', 'DashboardWorkspace.jsx'].map(file => ({ path: 'app/' + file,
  code: fs.readFileSync(path.join(root, 'frontend/workbench/app', file), 'utf8') }));
const compiled = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
for (const output of compiled.outputs) vm.runInNewContext(output.code, host, { filename: output.path });
const clone = value => JSON.parse(JSON.stringify(value)), W = host.window;
const original = { scope: { category: 'material', status: 'open', query: 'F-R2', sort: 'subject', direction: 'desc', page: 2, size: 10,
  source: 'production', snapshot_ref: 'old-process-snapshot' }, item_ref: 'a'.repeat(48), history_page: 2, tab: 'records' };
const before = clone(original), restored = W.WorkbenchDashboardWorkspace({ initialContext: original }).props.start;
const expected = clone(original.scope); delete expected.snapshot_ref;
assert.deepEqual(clone(restored.q), expected); assert.equal(restored.historyPage, 2); assert.equal(restored.selected, original.item_ref);
assert.deepEqual(original, before);
for (const scope of [{ ...original.scope, snapshot_ref: 19 }, { ...original.scope, unknown: true }]) {
  const result = W.WorkbenchDashboardWorkspace({ initialContext: { ...original, scope } });
  assert.equal(result.type, 'div'); assert(result.props.children.some(child => child && child.props && child.props.error));
}
const n = { view: 'gantt', enabled: true, context: { plan_ref: 'b'.repeat(48) } };
assert.equal(W.DashboardPanels.navigationTarget(n, () => {}), '计划甘特');
const negative = [() => W.DashboardPanels.navigationTarget({ ...n, view: 'unregistered-view' }, () => {}),
  () => W.DashboardPanels.navigationTarget({ ...n, view: 'constructor' }, () => {}),
  () => W.DashboardPanels.navigationTarget(n, undefined),
  () => W.DashboardPanels.navigationTarget({ ...n, enabled: false, reason: '' }, () => {}),
  () => W.DashboardPanels.navigationTarget({ ...n, context: [] }, () => {})];
for (const check of negative) assert.throws(check);
const oldSystem = { source: 'current', tab: 'backups', page_size: 10, records: {
  backups: { page: 2, filters: { query: 'original-file' }, snapshot_ref: 'old-scope', selection: { key: 'c'.repeat(64), backup_ref: 'old-file-token' } },
  logs: { page: 2, filters: { query: 'real-log' }, snapshot_ref: 'old-logs', selection: { key: 'stable-log-content' } }
} };
const saved = clone(oldSystem), result = W.SystemMaintenanceAPI.pageContext(oldSystem);
assert.equal(result.records.backups.page, 2); assert.equal(result.records.backups.selection.record_kind, 'backup_file');
assert.equal(result.records.backups.selection.key, 'c'.repeat(64)); assert.equal(result.records.logs.selection.key, 'stable-log-content');
assert(!/snapshot_ref|backup_ref/.test(JSON.stringify(result))); assert.deepEqual(oldSystem, saved);
const orphan = W.SystemMaintenanceAPI.pageContext({ ...oldSystem, records: { backups: { page: 2, snapshot_ref: 'old', selection: { backup_ref: 'legacy-only-token' } } } });
assert.equal(orphan.records.backups.selection.record_kind, 'backup_file'); assert.equal(orphan.records.backups.selection.key, undefined);
assert(!/legacy-only-token|backup_ref/.test(JSON.stringify(orphan)));
assert.throws(() => W.SystemMaintenanceAPI.pageContext({ records: { backups: { snapshot_ref: 17 } } }));
assert.throws(() => W.SystemMaintenanceAPI.pageContext({ records: { logs: { selection: { backup_ref: 'not-a-log-key' } } } }));
process.stdout.write(JSON.stringify({ passed: true, dashboard_negative: negative.length + 2, system_negative: 2,
  legacy_file_lease_not_identity: true, source: 'compiled production boundary functions; not a browser acceptance substitute' }) + '\n');
