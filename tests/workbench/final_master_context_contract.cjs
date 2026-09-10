'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {compile} = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const files = ['resource-contract.js', 'ResourceTableFilterModel.js', 'ProcessContract.js', 'ProcessReadView.js', 'BatchContract.js',
  'CalendarContract.js', 'MasterOverviewContract.js', 'ResourceWorkspace.jsx', 'ProcessWorkspace.jsx',
  'ResourceCalendar.jsx', 'BatchWorkspace.jsx', 'MasterOverviewWorkspace.jsx'];
const sources = files.map(name => ({path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
const compiled = compile({babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true});
const window = {ResourceControls: {}, BatchControls: {}, CalendarFields: {}, MasterOverviewTable: {}};
const context = vm.createContext({window, React: {}, console, URLSearchParams, Date, Number, JSON, Object, Array, Set, Map, Math});
compiled.outputs.forEach(item => vm.runInContext(item.code, context, {filename: item.path}));
const ref = 'a'.repeat(48), other = 'b'.repeat(48);
const clone = value => JSON.parse(JSON.stringify(value));
const equal = (left, right) => assert.deepEqual(clone(left), clone(right));
let cases = 0;
function check(name, callback) { callback(); cases++; console.log('PASS ' + name); }
const batch = {read_view: {scope: {query: 'FC-', page: 2, size: 20, sort: 'quantity', direction: 'desc', column_filters: {quantity: [1, 2, null]}},
  selected_refs: [ref], entity_ref: ref, sort_state: {key: 'quantity', direction: 'desc'}}};
check('batch-valid-roundtrip', () => { const value = window.BatchWorkspace.readContext(batch); assert.equal(value.scope.page, 2); equal(value.selected, [ref]); assert.equal(value.opened, ref); });
check('batch-focus-legacy-return', () => { const value = window.BatchWorkspace.readContext({focus: 'gaps', batchIds: ['FC-B1'], return_to: 'run'}); assert.equal(value.scope.focus, 'gaps'); assert.equal(value.sourceContext.return_to, 'run'); });
check('batch-dashboard-ref-alias', () => { const value = window.BatchWorkspace.readContext({entity_ref: ref, batch_ref: ref, plan_ref: other}); assert.equal(value.opened, ref); assert.equal(value.sourceContext.plan_ref, other); });
for (const [name, mutate] of [
  ['unknown-top', value => { value.request_key = 'forbidden'; }], ['write-context', value => { value.read_view.write_token = 'forbidden'; }],
  ['scope-snapshot', value => { value.read_view.scope.snapshot_ref = 'forbidden'; }], ['page-zero', value => { value.read_view.scope.page = 0; }],
  ['size-overflow', value => { value.read_view.scope.size = 101; }], ['invalid-status', value => { value.read_view.scope.status = 'unknown'; }],
  ['invalid-focus', value => { value.read_view.scope.focus = 'all'; }], ['unknown-column', value => { value.read_view.scope.column_filters.extra = []; }],
  ['object-value', value => { value.read_view.scope.column_filters.quantity = [{}]; }], ['bad-ref', value => { value.read_view.selected_refs = ['FC-B1']; }],
  ['duplicate-ref', value => { value.read_view.selected_refs.push(ref); }], ['bad-sort-state', value => { value.read_view.sort_state = false; }],
  ['mixed-locator', value => { value.focus = 'gaps'; }], ['mismatched-entity', value => { value.entity_ref = other; }],
]) check('batch-reject-' + name, () => { const value = clone(batch); mutate(value); assert.throws(() => window.BatchWorkspace.readContext(value)); });
check('batch-dashboard-alias-conflict', () => assert.throws(() => window.BatchWorkspace.readContext({entity_ref: ref, batch_ref: other})));
const resource = {source: 'production', kind: 'material', read_view: {scope: {query: 'MAT-', page: 2, size: 20, sort: 'stock_qty', direction: 'desc', status: ''},
  selected_refs: [ref], sort_active: true, detail: {kind: 'material', entity_ref: ref}}};
check('resource-valid-node-page-detail', () => { const value = window.ResourceWorkspace.navigation(resource); assert(!value.error); assert.equal(value.node, 'material'); assert.equal(value.context.read_view.scope.page, 2); });
for (const [name, mutate] of [
  ['unknown-top', value => { value.pending_request = {}; }], ['unknown-view', value => { value.read_view.input = {}; }],
  ['unknown-scope', value => { value.read_view.scope.snapshot_ref = 'old'; }], ['wrong-column', value => { value.read_view.scope.sort = 'default_days'; }],
  ['wrong-kind-category', value => { value.read_view.scope.category = 'internal'; }], ['bad-selection', value => { value.read_view.selected_refs = ['MAT-1']; }],
  ['bad-detail', value => { value.read_view.detail.kind = 'batch'; }], ['deep-plus-view', value => { value.entity_ref = ref; }],
]) check('resource-reject-' + name, () => { const value = clone(resource); mutate(value); assert(window.ResourceWorkspace.navigation(value).error); });
check('resource-nested-exact-kind', () => { const value = clone(resource); value.read_view.detail = {kind: 'op_type', category: 'external', entity_ref: other}; assert(!window.ResourceWorkspace.navigation(value).error); });
const processView = {scope: {query: 'PROC-', page: 2, size: 50, sort: [{field: 'label', direction: 'asc'}], stage: 'hours', column_filters: {}}, selected_refs: [ref], entity_ref: ref};
check('process-leaf-cold-without-any-workspace-or-react', () => {
  const coldWindow = {}, cold = vm.createContext({window: coldWindow, URLSearchParams, Date, Number, JSON, Object, Array, Set, Map, Math});
  const pure = new Set(['app/resource-contract.js', 'app/ResourceTableFilterModel.js', 'app/ProcessContract.js', 'app/ProcessReadView.js']);
  compiled.outputs.filter(item => pure.has(item.path)).forEach(item => vm.runInContext(item.code, cold, {filename: item.path}));
  assert.equal(coldWindow.ResourceWorkspace, undefined); assert.equal(coldWindow.ProcessWorkspace, undefined);
  equal(coldWindow.APSProcessReadView.read(processView), processView);
  assert.equal(window.ProcessWorkspace.readView, window.APSProcessReadView.read);
});
check('process-valid-view', () => equal(window.ProcessWorkspace.readView(processView), processView));
check('process-navigation-view', () => assert(!window.ResourceWorkspace.navigation({source: 'production', kind: 'part', read_view: processView}).error));
for (const [name, mutate] of [
  ['unknown-view', value => { value.write_token = 'x'; }], ['bad-stage', value => { value.scope.stage = 'unknown'; }],
  ['bad-sort', value => { value.scope.sort = [{field: 'op_id', direction: 'asc'}]; }], ['unknown-filter', value => { value.scope.column_filters.op_id = {}; }],
  ['wrong-ref', value => { value.entity_ref = 'PROC-1'; }], ['duplicate-selection', value => { value.selected_refs.push(ref); }],
]) check('process-reject-' + name, () => { const value = clone(processView); mutate(value); assert.throws(() => window.ProcessWorkspace.readView(value)); });
const master = {read_view: {scope: {view: 'entities', domain: 'material', query: 'MAT-', size: 20}, page: 2,
  selected: {domain: 'material', entity_ref: ref}, section: 'fields', detail_page: 1}};
check('master-valid-view', () => { const value = window.MasterOverviewWorkspace.readContext(master); assert.equal(value.page, 2); assert.equal(value.selected.entity_ref, ref); assert.equal(value.section, 'fields'); });
check('master-legacy-deep-link', () => assert.equal(window.MasterOverviewWorkspace.readContext({domain: 'material', entity_ref: ref}).initial.entity_ref, ref));
for (const [name, mutate] of [
  ['unknown-top', value => { value.preview_ref = 'x'; }], ['mixed-deep', value => { value.entity_ref = ref; }],
  ['unknown-view', value => { value.read_view.write_token = 'x'; }], ['bad-page', value => { value.read_view.page = 0; }],
  ['bad-section', value => { value.read_view.section = 'edit'; }], ['bad-selection', value => { value.read_view.selected.entity_ref = 'MAT-1'; }],
]) check('master-reject-' + name, () => { const value = clone(master); mutate(value); assert.throws(() => window.MasterOverviewWorkspace.readContext(value)); });
check('calendar-month-ref', () => assert(!window.ResourceWorkspace.navigation({source: 'production', kind: 'calendar', month: '2026-09', date: '2026-09-09'}).error));
check('calendar-month-date-mismatch', () => assert(window.ResourceWorkspace.navigation({source: 'production', kind: 'calendar', month: '2026-09', date: '2026-10-09'}).error));
check('calendar-does-not-accept-editor-state', () => assert(window.ResourceWorkspace.navigation({source: 'production', kind: 'calendar', month: '2026-09', read_view: {draft: {}}}).error));
async function readChecks() {
  const signal = {}, scope = clone(processView.scope), originalScope = clone(scope);
  function processPage(request, snapshot = 'new-read-snapshot') {
    return {ok: true, schema_version: 1, meta: {source: 'production', time_basis: 'factory_local', snapshot_ref: snapshot, request_ref: 'unit-read', as_of: '2026-09-10T00:00:00'}, warnings: [],
      data: {entities: [], page: {number: request.page, size: request.size, total: 123, pages: Math.ceil(123 / request.size), sort: clone(window.APSProcessContract.ordering(request))},
        capabilities: {create: true, delete: true, export: true, import: true, route_preview: true, stage_confirm: true}, create_context: null,
        metrics: {counts: {total: 123, route: 0, source: 0, hours: 123, ready: 0}}}};
  }
  async function checked(name, callback) { await callback(); cases++; console.log('PASS ' + name); }
  await checked('process-restored-page-uses-new-same-scope-snapshot', async () => {
    const calls = [];
    await window.ProcessWorkspace.readList({list: async (kind, request, givenSignal) => { assert.equal(kind, 'part'); assert.equal(givenSignal, signal); calls.push(clone(request)); return processPage(request); }}, scope, signal);
    equal(calls, [{...scope, page: 1}, {...scope, snapshot_ref: 'new-read-snapshot'}]); equal(scope, originalScope);
  });
  await checked('process-existing-snapshot-is-not-replaced', async () => {
    const calls = [], request = {...scope, snapshot_ref: 'existing-read-snapshot'};
    await window.ProcessWorkspace.readList({list: async (_kind, next) => { calls.push(clone(next)); return processPage(next, request.snapshot_ref); }}, request, signal);
    equal(calls, [request]);
  });
  await checked('process-first-page-needs-one-read-only', async () => {
    const calls = [], request = {...scope, page: 1};
    await window.ProcessWorkspace.readList({list: async (_kind, next) => { calls.push(clone(next)); return processPage(next); }}, request, signal);
    equal(calls, [request]);
  });
  for (const fault of ['first-failure', 'demo-first', 'changed-snapshot', 'changed-page']) await checked('process-restore-rejects-' + fault, async () => {
    const calls = [], adapter = {list: async (_kind, request) => {
      calls.push(clone(request)); if (fault === 'first-failure') throw new Error('Original first read failed');
      const result = processPage(request);
      if (fault === 'demo-first') result.meta.source = 'demo';
      if (request.page === 2 && fault === 'changed-snapshot') result.meta.snapshot_ref = 'other-snapshot';
      if (request.page === 2 && fault === 'changed-page') result.data.page.number = 1;
      return result;
    }};
    await assert.rejects(() => window.ProcessWorkspace.readList(adapter, scope, signal));
    assert.equal(calls.length, ['first-failure', 'demo-first'].includes(fault) ? 1 : 2); equal(scope, originalScope);
  });
  await checked('master-restored-page-uses-new-same-scope-snapshot', async () => {
    const calls = [], masterScope = window.MasterOverviewWorkspace.readContext(master).scope;
    const api = {list: async (givenScope, page, token, givenSignal) => { assert.equal(givenSignal, signal); calls.push({scope: clone(givenScope), page, token}); return {meta: {snapshot_ref: 'fresh-master'}}; }};
    await window.MasterOverviewWorkspace.readList(api, masterScope, 2, undefined, signal);
    equal(calls, [{scope: masterScope, page: 1}, {scope: masterScope, page: 2, token: 'fresh-master'}]);
  });
  await checked('master-existing-snapshot-is-not-replaced', async () => {
    const calls = [], api = {list: async (_scope, page, token) => { calls.push({page, token}); return {}; }};
    await window.MasterOverviewWorkspace.readList(api, {}, 2, 'existing-master', signal);
    equal(calls, [{page: 2, token: 'existing-master'}]);
  });
  for (const failAt of [1, 2]) await checked('master-rejected-read-does-not-reset-page-' + failAt, async () => {
    const calls = [], api = {list: async (_scope, page, token) => { calls.push({page, token}); if (page === failAt) throw new Error('Original read rejected'); return {meta: {snapshot_ref: 'fresh-master'}}; }};
    await assert.rejects(() => window.MasterOverviewWorkspace.readList(api, {}, 2, undefined, signal)); assert.equal(calls.length, failAt);
  });
  console.log(JSON.stringify({cases, failed: 0, scope: 'unit read-context and request sequencing contracts; not browser or backend acceptance'}));
}
readChecks().catch(error => { console.error(error); process.exitCode = 1; });
