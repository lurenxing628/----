'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {compile} = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..');
const files = ['resource-contract.js', 'BatchContract.js', 'BatchWorkspace.jsx', 'DashboardContract.js', 'DashboardSession.js'];
const sources = files.map(name => ({path: 'app/' + name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8')}));
const compiled = compile({babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true});
const ref = 'a'.repeat(48), cases = [];
const clone = value => JSON.parse(JSON.stringify(value));
const equal = (left, right) => assert.deepEqual(clone(left), clone(right));
function check(name, callback) {
  try { callback(); cases.push({name, status: 'passed'}); }
  catch (error) { cases.push({name, status: 'failed', error: error.stack}); }
}
function freeze(value) {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
  return value;
}

// Inspect parser and button wiring without executing reads or fabricating successful API data.
let renderState;
const Button = Symbol('Button'), ErrorBox = Symbol('ErrorBox');
const window = {ResourceControls: {Button, ErrorBox}, BatchControls: {Styles: Symbol('Styles')}, BatchTable: Symbol('BatchTable'),
  WorkbenchGuards: {useDirtyGuard: () => 'batch-contract-test'},
  APSResourceSession: {
    useCommand: () => ({phase: 'idle', locked: false}),
    useQuery: (_load, _dependencies, enabled) => {
      renderState.queryEnabled = enabled;
      return {result: null, loading: false, error: null};
    }
  }, WorkbenchPageContext: {useSnapshot: (value, enabled) => { renderState.snapshot = {value, enabled}; }}};
const React = {Fragment: Symbol('Fragment'), createElement: (type, props, ...children) => ({type, props: {...props, children}}),
  useState: value => [typeof value === 'function' ? value() : value, () => { throw new Error('Unexpected state mutation'); }],
  useRef: value => ({current: value}), useEffect: () => {}};
const globals = {console, URLSearchParams, Date, Number, JSON, Object, Array, Set, Map, Math};
const batchVM = vm.createContext({...globals, window, React});
compiled.outputs.filter(item => !item.path.includes('/Dashboard')).forEach(item => vm.runInContext(item.code, batchVM, {filename: item.path}));
const dashboardWindow = {}, dashboardVM = vm.createContext({...globals, window: dashboardWindow});
compiled.outputs.filter(item => item.path.includes('/Dashboard')).forEach(item => vm.runInContext(item.code, dashboardVM, {filename: item.path}));
const read = window.BatchWorkspace.readContext;
const context = freeze({scope: {category: 'material', status: 'following', query: 'B1', sort: 'deadline', direction: 'desc', page: 3, size: 10},
  tab: 'records', item_ref: ref, history_page: 4});
const target = freeze({view: 'dashboard', context});
function restored(value) {
  return {read_view: {scope: {query: 'B1', page: 2, size: 20, sort: 'quantity', direction: 'desc', column_filters: {quantity: [1, 2]}},
    selected_refs: [ref], entity_ref: ref, sort_state: {key: 'quantity', direction: 'desc'}, source_context: {batch_ref: ref, return_to: value}}};
}
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  return value && typeof value === 'object' && 'type' in value ? [value, ...nodes(value.props.children)] : [];
}
function render(initialContext) {
  const calls = [];
  renderState = {};
  const tree = window.BatchWorkspace({initialContext, onNav: (...args) => calls.push(args)}), all = nodes(tree);
  const back = all.find(node => node.type === Button && ['返回值班台', '返回排产'].includes(node.props.children[0]));
  assert(back, 'The real BatchWorkspace return button must exist');
  return {back, calls, all, state: renderState};
}

check('typed-direct-envelope-is-preserved', () => {
  const initial = freeze({entity_ref: ref, batch_ref: ref, return_to: target}), before = clone(initial), value = read(initial);
  assert.equal(value.opened, ref); assert.equal(value.sourceContext.return_to, target); assert.equal(value.sourceContext.return_to.context, context);
  equal(initial, before); assert.equal(window.DashboardSession, undefined); assert.equal(window.WorkbenchDashboardWorkspace, undefined);
});
check('typed-restored-envelope-is-preserved', () => {
  const initial = freeze(restored(target)), before = clone(initial), value = read(initial);
  assert.equal(value.scope.page, 2); equal(value.selected, [ref]); assert.equal(value.opened, ref);
  assert.equal(value.sourceContext.return_to, target); equal(initial, before);
});
check('typed-return-button-keeps-original-dashboard-state', () => {
  const value = render({return_to: target});
  assert.equal(value.back.props.disabled, false); assert.equal(value.back.props.children[0], '返回值班台');
  value.back.props.onClick(); assert.equal(value.calls.length, 1); assert.equal(value.calls[0].length, 2);
  assert.equal(value.calls[0][0], 'dashboard'); assert.equal(value.calls[0][1], context);
  const restoredDashboard = dashboardWindow.DashboardSession.context(value.calls[0][1]);
  assert.equal(restoredDashboard.q.page, 3); assert.equal(restoredDashboard.q.query, 'B1'); assert.equal(restoredDashboard.q.status, 'following');
  assert.equal(restoredDashboard.tab, 'records'); assert.equal(restoredDashboard.selected, ref); assert.equal(restoredDashboard.historyPage, 4);
});
for (const legacy of ['run', 'dashboard']) check('legacy-string-' + legacy, () => {
  assert.equal(read({return_to: legacy}).sourceContext.return_to, legacy);
  assert.equal(read(restored(legacy)).sourceContext.return_to, legacy);
  const value = render({return_to: legacy}); value.back.props.onClick(); equal(value.calls, [[legacy]]);
  assert.equal(value.back.props.children[0], legacy === 'dashboard' ? '返回值班台' : '返回排产');
});
check('absent-return-keeps-run-default', () => { const value = render(undefined); value.back.props.onClick(); equal(value.calls, [['run']]); });
check('opaque-body-is-preserved-for-dashboard-owned-validation', () => {
  const invalidBody = freeze({...context, tab: 'unsupported-tab'}), envelope = freeze({view: 'dashboard', context: invalidBody});
  assert.equal(read({return_to: envelope}).sourceContext.return_to.context, invalidBody);
  const value = render({return_to: envelope}); value.back.props.onClick(); assert.equal(value.calls[0][1], invalidBody);
  assert.throws(() => dashboardWindow.DashboardSession.context(value.calls[0][1]));
});
check('opaque-extra-body-field-is-not-silently-dropped', () => {
  const invalidBody = freeze({...context, unsupported_field: true}), envelope = {view: 'dashboard', context: invalidBody};
  assert.equal(read({return_to: envelope}).sourceContext.return_to.context, invalidBody);
  assert.throws(() => dashboardWindow.DashboardSession.context(invalidBody));
});
const invalid = [
  ['unknown-view', {view: 'analysis', context}], ['object-run', {view: 'run', context}], ['view-type', {view: 1, context}],
  ['missing-view', {context}], ['missing-context', {view: 'dashboard'}], ['extra-envelope-field', {...target, extra: true}],
  ['null-envelope', null], ['array-envelope', []], ['number-envelope', 1], ['boolean-envelope', false], ['unknown-string', 'analysis'],
  ...[null, undefined, [], '', 1, false, () => ({})].map((value, index) => ['context-type-' + index, {view: 'dashboard', context: value}])
];
for (const [name, value] of invalid) {
  check('reject-direct-' + name, () => assert.throws(() => read({return_to: value}), /批次来源引用或返回入口不正确/));
  check('reject-restored-' + name, () => assert.throws(() => read(restored(value)), /批次来源引用或返回入口不正确/));
}
check('invalid-envelope-blocks-read-and-return', () => {
  const value = render({return_to: {...target, extra: true}});
  assert.equal(value.state.queryEnabled, false); assert.equal(value.back.props.disabled, true); equal(value.calls, []);
  assert(value.all.some(node => node.type === ErrorBox && node.props.error && /批次来源引用或返回入口不正确/.test(node.props.error.message)));
});
const failed = cases.filter(row => row.status === 'failed');
console.log(JSON.stringify({scope: 'batch_dashboard_return', cases: cases.length, failed: failed.length, checks: cases}));
if (failed.length) process.exitCode = 1;
