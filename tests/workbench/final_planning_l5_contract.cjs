'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm'), crypto = require('node:crypto');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), vendor = path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex'), plain = value => JSON.parse(JSON.stringify(value));
const checks = [], check = (name, run) => { run(); checks.push(name); }, ref = n => n.toString(16).padStart(48, '0');
function memory() {
  const values = new Map();
  return { values, writes: [], removed: [], failRead: false, failWrite: false, failClear: false,
    getItem(key) { if (this.failRead) throw new Error('read denied'); return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { if (this.failWrite) throw new Error('write denied'); this.writes.push(key); values.set(key, value); },
    removeItem(key) { if (this.failClear) throw new Error('clear denied'); this.removed.push(key); values.delete(key); } };
}
const store = memory(), context = vm.createContext({ console }); context.window = context; context.self = context;
context.localStorage = store; context.history = { state: null, replaceState(value) { this.state = value; } }; context.location = { href: '/workbench/trial' };
context.addEventListener = () => {}; context.removeEventListener = () => {}; context.dispatchEvent = () => {};
context.CustomEvent = class { constructor(type, options) { this.type = type; this.detail = options.detail; } };
vm.runInContext(fs.readFileSync(path.join(vendor, 'react-18.3.1.js'), 'utf8'), context);
const names = ['resource-contract.js', 'PointContract.js', 'PlanGanttModel.js', 'ResourceControls.jsx', 'TrialContract.js', 'TrialControls.jsx',
  'TrialViewState.js', 'TrialGantt.jsx', 'TrialAdoptionHistoryState.js', 'TrialResults.jsx', 'PlanDetailsUI.jsx', 'PlanWorkspace.jsx'];
const sources = names.map(name => ({ path: 'frontend/workbench/app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const built = compile({ babel_path: path.join(vendor, 'babel-7.29.0.min.js'), sources, check_combined: true });
context.TrialAdoptionHistoryAPI = { states: ['all', 'current', 'historical', 'unavailable'] };
for (const output of built.outputs) if (!output.path.endsWith('/PlanWorkspace.jsx')) vm.runInContext(output.code, context, { filename: output.path });
const V = context.TrialViewState, draft = { draft_ref: ref(1), scope: { resource_type: 'operator', query: 'original scope' } };
const target = V.identity(draft), initial = V.defaults(draft), sameRefScenario = { draft_ref: ref(2), scenario_ref: ref(1), scope: {} };
function render(Component, props) {
  const internals = context.React.__SECRET_INTERNALS_DO_NOT_USE_OR_YOU_WILL_BE_FIRED;
  const old = internals.ReactCurrentDispatcher.current;
  internals.ReactCurrentDispatcher.current = { useState: value => [typeof value === 'function' ? value() : value, () => {}],
    useMemo: create => create(), useRef: current => ({ current }), useEffect: () => {}, useLayoutEffect: () => {} };
  try { return Component(props); } finally { internals.ReactCurrentDispatcher.current = old; }
}
function nodes(value, predicate) {
  if (Array.isArray(value)) return value.flatMap(item => nodes(item, predicate));
  if (!value || typeof value !== 'object') return [];
  return (predicate(value) ? [value] : []).concat(nodes(value.props && value.props.children, predicate));
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  if (value === null || value === undefined || typeof value === 'boolean') return '';
  return typeof value === 'object' ? text(value.props && value.props.children) : String(value);
}
check('No record preserves original scope/query without writing defaults', () => {
  assert.equal(V.read(target, store), null);
  assert.deepEqual(plain(initial), { mode: 'operator', baseline: true, only_changed: false, query: 'original scope', result_tab: 'delivery' });
  render(() => V.useView(draft)); assert.equal(store.writes.length, 0);
});
check('Five preferences round-trip; a later tab patch preserves gantt fields', () => {
  V.write(target, initial, { mode: 'batch', baseline: false, only_changed: true, query: 'saved query' }, store);
  V.write(target, initial, { result_tab: 'capacity' }, store);
  assert.deepEqual(plain(V.read(target, store)), { mode: 'batch', baseline: false, only_changed: true, query: 'saved query', result_tab: 'capacity' });
  const raw = JSON.parse(store.getItem(V.key(target)));
  assert.deepEqual(Object.keys(raw).sort(), ['kind', 'preferences', 'ref', 'schema_version']);
  assert.deepEqual(Object.keys(raw.preferences).sort(), ['baseline', 'mode', 'only_changed', 'query', 'result_tab']);
});
check('Draft and scenario kinds remain isolated even with the same reference', () => {
  const scenarioTarget = V.identity(sameRefScenario);
  assert.notEqual(V.key(target), V.key(scenarioTarget)); assert.equal(V.read(scenarioTarget, store), null);
  V.write(scenarioTarget, V.defaults(sameRefScenario), { query: 'scenario only' }, store);
  assert.equal(V.read(target, store).query, 'saved query');
});
for (const patch of [{ write_token: 'forbidden' }, { read_token: 'forbidden' }, { tasks: [] }, { baseline: 1 },
  { only_changed: 'yes' }, { mode: 'supplier' }, { query: 'x'.repeat(201) }, { result_tab: 'unknown' }]) {
  check('Reject preference patch ' + Object.keys(patch)[0] + ':' + String(Object.values(patch)[0]).slice(0, 10), () => {
    const before = store.getItem(V.key(target)); assert.throws(() => V.write(target, initial, patch, store));
    assert.equal(store.getItem(V.key(target)), before);
  });
}
for (const replace of [v => { v.schema_version = '1'; }, v => { v.schema_version = 2; }, v => { v.ref = ref(9); },
  v => { v.kind = 'scenario'; }, v => { v.preferences.read_token = 'forbidden'; }, v => { v.preferences.baseline = null; }]) {
  check('Reject invalid stored schema/identity/fields without overwrite #' + checks.length, () => {
    const broken = memory(), record = JSON.parse(store.getItem(V.key(target))); replace(record);
    broken.values.set(V.key(target), JSON.stringify(record));
    assert.throws(() => V.read(target, broken)); assert.throws(() => V.write(target, initial, { query: 'new' }, broken));
    assert.equal(broken.writes.length, 0); assert.equal(broken.removed.length, 0);
  });
}
check('Identity types are checked, not coerced', () => {
  for (const value of [{ draft_ref: 1 }, { draft_ref: ref(1), scenario_ref: null }, { draft_ref: ref(1), scenario_ref: [] }]) assert.throws(() => V.identity(value));
  assert.throws(() => V.key({ kind: 'draft', ref: ref(1), token: 'not allowed' }));
});
check('Corrupt and denied storage have explicit error and targeted recovery controls', () => {
  const name = V.key(target), before = store.getItem(name); store.values.set(name, '{broken');
  const blocked = render(() => V.useView(draft)); assert.equal(blocked.value, null); assert(blocked.error);
  const notice = V.Notice({ state: blocked, label: 'test preference' });
  assert.equal(nodes(notice, node => node.type === context.TrialControls.Button).length, 2);
  assert.equal(store.getItem(name), '{broken');
  blocked.reset(); assert.equal(store.getItem(name), null);
  assert.equal(V.read(V.identity(sameRefScenario), store).query, 'scenario only');
  store.values.set(name, before); store.failRead = true;
  assert.equal(render(() => V.useView(draft)).error.code, 'read_unavailable'); store.failRead = false;
  store.failWrite = true; assert.throws(() => V.write(target, initial, { query: 'pending' }, store), { code: 'write_unavailable' });
  assert.equal(store.getItem(name), before); store.failWrite = false;
  V.write(target, initial, { query: 'pending' }, store); assert.equal(V.read(target, store).query, 'pending');
  store.failClear = true; assert.throws(() => V.clear(target, store), { code: 'clear_unavailable' }); store.failClear = false;
});
const resultData = value => ({ ...value, resources: { machines: [], operators: [] }, comparison: { batches: [] },
  capacity: { resources: [] }, change_history: [], unplanned_operations: [], validation: { issues: [] }, tasks: [] });
function selectedTab(data) {
  const tree = render(context.TrialResults.Results, { data: resultData(data), onSelect: () => {} });
  const tabs = nodes(tree, node => node.type === context.TrialControls.Tabs);
  return { tree, tab: tabs[0] && tabs[0].props.value };
}
check('A fresh draft or scenario entry restores LS, not history defaults', () => {
  context.history.state = null;
  assert.equal(selectedTab(draft).tab, 'capacity');
  V.write(V.identity(sameRefScenario), V.defaults(sameRefScenario), { result_tab: 'tasks' }, store);
  assert.equal(selectedTab(sameRefScenario).tab, 'tasks');
});
check('Only an actual matching explicit history entry overrides LS', () => {
  const saved = { scenario_ref: sameRefScenario.scenario_ref, tab: 'history', status: 'all', page: 1, size: 20 };
  context.history.state = { trialAdoptionHistory: saved };
  const before = store.getItem(V.key(V.identity(sameRefScenario)));
  assert.equal(selectedTab(sameRefScenario).tab, 'history'); assert.equal(store.getItem(V.key(V.identity(sameRefScenario))), before);
  context.history.state = { trialAdoptionHistory: { ...saved, scenario_ref: ref(9) } };
  assert.equal(selectedTab(sameRefScenario).tab, 'tasks');
});
check('Malformed matching history is visible and clearing it preserves other history', () => {
  context.history.state = { workbench: { key: 17 }, trialAdoptionHistory: { scenario_ref: sameRefScenario.scenario_ref, tab: 'bad' } };
  const { tree, tab } = selectedTab(sameRefScenario); assert.equal(tab, undefined);
  assert(nodes(tree, node => node.type === context.TrialControls.ErrorBox).length);
  const reset = nodes(tree, node => node.type === context.TrialControls.Button && text(node) === '清除本页页签记录')[0];
  assert(reset); reset.props.onClick(); assert.deepEqual(plain(context.history.state), { workbench: { key: 17 } });
  assert.equal(selectedTab(sameRefScenario).tab, 'tasks');
});

function plan(state = 'available', count = 2) {
  const scope = { range_start: '2026-09-09T08:00:00', range_end: '2026-09-09T09:00:00', selection: 'overlap', boundary: 'half_open', time_basis: 'factory_local' };
  return { plan: { plan_ref: ref(20) }, scope: { range_start: null }, time_scope: scope, tasks: [], resources: [], projections: {
    calendar: { resources: [] }, occupancy: { basis: 'selected_plan_only', plan_ref: ref(20), time_scope: { ...scope }, state, issues: [], resources: [
      { kind: 'machine', resource_ref: ref(21), label: 'M1', has_overlap: count > 1,
        segments: [{ start: '2026-09-09T08:30:00', end: '2026-09-09T08:45:00', concurrent_operations: count }] }
    ] } } };
}
check('Overlap details consume the projection, not visible task counts; input is unchanged', () => {
  const data = plan(), before = JSON.stringify(data), value = context.PlanDetailsUI.conflictRows(data);
  assert.equal(value.rows.length, 1); assert.equal(value.rows[0].concurrent_operations, 2);
  assert.equal(JSON.stringify(data), before); data.tasks = [{ task_ref: ref(99) }];
  assert.equal(context.PlanDetailsUI.conflictRows(data).rows[0].concurrent_operations, 2);
});
for (const count of [null, undefined, '2', 0, 1.5]) check('Unknown/invalid concurrency cannot become zero: ' + String(count), () => {
  const data = plan(); data.projections.occupancy.resources[0].segments[0].concurrent_operations = count;
  assert.throws(() => context.PlanDetailsUI.conflictRows(data));
});
check('Identity, time scope and missing positive-overlap detail fail visibly', () => {
  for (const mutate of [d => { d.projections.occupancy.plan_ref = ref(9); }, d => { d.projections.occupancy.time_scope.range_end = '2026-09-10T09:00:00'; },
    d => { d.projections.occupancy.resources[0].segments = []; }]) {
    const data = plan(); mutate(data); assert.throws(() => context.PlanDetailsUI.conflictRows(data));
    assert(nodes(render(context.PlanDetailsUI.Conflicts, { data }), node => node.type === context.ResourceControls.ErrorBox).length);
  }
});
check('Known empty, no overlap, partial and unavailable stay distinct', () => {
  const empty = plan(); empty.projections.occupancy.resources = [];
  assert(text(render(context.PlanDetailsUI.Conflicts, { data: empty })).includes('没有资源占用记录'));
  assert(text(render(context.PlanDetailsUI.Conflicts, { data: plan('available', 1) })).includes('未发现资源安排重叠'));
  for (const state of ['partial', 'unavailable']) {
    const missing = plan(state, 1), label = text(render(context.PlanDetailsUI.Conflicts, { data: missing }));
    assert(label.includes('不能认定为没有重叠')); assert(!label.includes('未发现资源安排重叠'));
    assert(text(render(context.PlanDetailsUI.Conflicts, { data: plan(state) })).includes('未知部分不计为零'));
  }
});
check('Only the delay caller renders conflict details, with explicit slice and non-cause wording', () => {
  const workspace = sources.find(row => row.path.endsWith('/PlanWorkspace.jsx')).code;
  assert.equal((workspace.match(/<Conflicts\b/g) || []).length, 1);
  assert(workspace.includes("{view === 'delay' && <Conflicts"));
  const data = plan(); data.scope.range_start = data.time_scope.range_start;
  const rendered = text(render(context.PlanDetailsUI.Conflicts, { data }));
  assert(rendered.includes('当前读取切片，不代表整份计划')); assert(rendered.includes('不代表等待、停机、缺料或延期原因'));
});
const evidence = sources.map(row => ({ path: row.path, sha256: hash(Buffer.from(row.code)) }));
assert(evidence.every(row => hash(fs.readFileSync(path.join(root, row.path))) === row.sha256));
console.log(JSON.stringify({ contract_only: true, browser_or_full_entry_evidence: false, build_order_modified: false,
  compile_target: built.target, checks, sources: evidence }));
