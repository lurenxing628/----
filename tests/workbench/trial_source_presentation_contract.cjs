'use strict';
// No browser: exercise current component functions and their source-selection state.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), files = ['TrialControls.jsx', 'TrialCatalog.jsx'];
const sources = files.map(name => ({ path: name, code: fs.readFileSync(path.join(root, 'frontend/workbench/app', name), 'utf8') }));
const output = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources, check_combined: true });
let slots = [], index = 0, response;
const state = initial => {
  const at = index++;
  if (!(at in slots)) slots[at] = typeof initial === 'function' ? initial() : initial;
  return [slots[at], value => { slots[at] = typeof value === 'function' ? value(slots[at]) : value; }];
};
const React = { Fragment: 'Fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), useState: state,
  useRef: value => state(() => ({ current: value }))[0], useReducer: (reduce, value) => { const [current, set] = state(value); return [current, arg => set(old => reduce(old, arg))]; } };
const window = { ResourceControls: { Button: 'Button', Icon: 'Icon', Modal: 'Modal' }, TrialAPI: {}, TrialContract: {},
  WorkbenchFormat: { dateTime: value => value, number: value => String(value) },
  WorkbenchGuards: { useDirtyGuard: () => 'guard' }, WorkbenchReference: 'Reference',
  TrialSession: { useRead: (_load, _deps, enabled = true) => enabled && response ? { result: response } : {} } };
const context = vm.createContext({ React, window, console });
output.outputs.forEach(row => vm.runInContext(row.code, context));
const U = window.TrialControls, Create = window.TrialCatalog.Create;
function treeNodes(value) {
  if (Array.isArray(value)) return value.flatMap(treeNodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...treeNodes(value.props && value.props.children), ...treeNodes(value.props && value.props.footer)];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  return value && typeof value === 'object' ? text(value.props && value.props.children) : typeof value === 'string' ? value : '';
}
function render(component, props) { index = 0; return component(props); }
const candidateRef = 'a'.repeat(48), planRef = 'b'.repeat(48);
const props = { initialBase: { candidate_ref: candidateRef }, commands: { restore() {}, blocked: false, busy: false, key: null }, onClose() {} };
let view = render(Create, props);
assert(text(view).includes('来源类型：排产候选'));
assert(!treeNodes(view).some(node => typeof node.type === 'function' && node.type.name === 'SourceCatalog'));
assert(!text(view).includes('指定原来源'));
assert.equal(treeNodes(view).find(node => node.type === 'Reference').props.value, candidateRef);
const click = label => treeNodes(view).find(node => node.type === 'Button' && text(node) === label).props.onClick();
click('核对原来源');
response = { data: { base_identity: { candidate_ref: candidateRef, display_name: '高压候选2' }, task_count: 2, validation: { issues: [] }, write_context: { write_token: 'token' } } };
view = render(Create, props);
assert(text(view).includes('已选择：高压候选2'));
assert(text(view).includes('来源类型：排产候选'));
click('更换来源'); view = render(Create, props);
const picker = treeNodes(view).find(node => typeof node.type === 'function' && node.type.name === 'SourceCatalog');
assert(picker);
slots = []; response = null;
const catalog = render(picker.type, picker.props);
const tabs = treeNodes(catalog).find(node => node.type === U.Tabs);
assert.equal(tabs.props.value, 'candidate');
slots = []; view = render(Create, { ...props, initialBase: { plan_ref: planRef } });
assert(text(view).includes('来源类型：正式计划'));
const legacy = { code: 'scenario_adoption_not_connected', severity: 'blocker', message: '旧能力说明' };
const blocker = { code: 'resource_overlap', severity: 'blocker', message: '设备时段冲突' };
const warning = { code: 'ready_unknown', severity: 'warning', message: '齐套日期未知' };
assert(text(U.Issues({ rows: [legacy] })).includes('未发现约束问题'));
const issues = U.Issues({ rows: [legacy, blocker, warning] });
assert.deepEqual(Array.from(issues.props.rows), [blocker, warning]);
assert.equal(issues.props.columns[0][1](blocker), '冲突');
assert.equal(issues.props.columns[0][1](warning), '提示');
assert.equal(legacy.severity, 'blocker');
window.TrialContract.check = condition => { if (!condition) throw Error('invalid fixture'); };
window.TrialContract.workspace = () => {};
window.APSSystemWorkbench = { csvCell: value => '"' + value.replaceAll('"', '""') + '"' };
vm.runInContext(fs.readFileSync(path.join(root, 'frontend/workbench/app/TrialExport.js'), 'utf8'), context);
const historical = { status: 'saved', base: { candidate_ref: candidateRef }, base_identity: { display_name: '原候选' }, task_count: 1,
  validation: { status: 'blocked', constraints_status: 'valid', issues: [legacy] }, unplanned_operations: [],
  tasks: [{ batch_ref: 'batch', changed: false, machine_ref: 'machine', original: { machine_ref: 'machine' } }],
  comparison: { changeovers: 0, batches: [{ batch_ref: 'batch', changed: false, moved: false, batch_id: 'B1' }] } };
const original = JSON.stringify(historical);
assert(window.TrialExport.csv(historical).text.includes('约束检查：通过；整体状态：通过；问题 0 项'));
assert.equal(JSON.stringify(historical), original);
assert.equal(JSON.stringify(JSON.parse(window.TrialExport.raw(historical).text)), original);
historical.validation.constraints_status = 'blocked'; historical.validation.issues.push(blocker);
assert(window.TrialExport.csv(historical).text.includes('问题 1 项'));
assert(window.TrialExport.csv(historical).text.includes('有冲突，不能采用'));
console.log('trial inherited source, exact preview identity and legacy capability presentation passed');
