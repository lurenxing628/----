'use strict';
// Source components only; no browser, global build or business database writes.
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs'), F = require('./plan_ui_fixtures.cjs');
const root = path.resolve(__dirname, '../..'), directory = path.join(root, 'frontend/workbench/app');
let slots = [], index = 0;
const React = { Fragment: 'Fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
  useMemo: fn => fn(), useState: initial => {
    const at = index++; if (!(at in slots)) slots[at] = typeof initial === 'function' ? initial() : initial;
    return [slots[at], value => { slots[at] = value; }];
  } };
const window = { ResourceControls: { Button: 'Button', Issues: 'Issues' }, WorkbenchControls: { Pager: 'Pager', EmptyState: 'Empty' },
  TrialViewState: { Notice: 'Notice', useView: () => ({ value: { result_tab: 'capacity' } }) },
  TrialGantt: { resourceNames: data => ref => data.resources.machines.concat(data.resources.operators).find(r => r.ref === ref)?.label || ref } };
const context = vm.createContext({ React, window, history: { state: null }, console });
for (const name of ['WorkbenchFormat.js', 'WorkbenchTerms.js', 'resource-contract.js', 'PointContract.js', 'PlanProcessOrder.js', 'PlanContract.js', 'PointGanttModel.js', 'PlanGanttModel.js', 'TrialContract.js']) {
  vm.runInContext(fs.readFileSync(path.join(directory, name), 'utf8'), context, { filename: name });
}
const files = ['PlanDetailsUI.jsx', 'TrialControls.jsx', 'TrialResults.jsx'];
const output = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: files.map(name => ({ path: name, code: fs.readFileSync(path.join(directory, name), 'utf8') })), check_combined: true });
output.outputs.forEach(row => vm.runInContext(row.code, context));
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props && value.props.children)];
}
function text(value) {
  if (Array.isArray(value)) return value.map(text).join('');
  return value && typeof value === 'object' ? text(value.props && value.props.children) : value == null ? '' : String(value);
}
function render(component, props, initial = []) { slots = initial; index = 0; return component(props); }
const clone = value => JSON.parse(JSON.stringify(value)), checks = [];
function check(label, action) { action(); checks.push(label); }
const plan = F.workspace(F.ref(1), {}, { count: 1 }).data, task = plan.tasks[0];
const draft = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
check('real overnight trial DTO uses calendar intersection', () => window.TrialContract.workspace(draft));
check('trial rejects missing numerator rather than displaying an invented zero', () => {
  const bad = clone(draft); delete bad.capacity.resources[0].available_occupied_hours;
  assert.throws(() => window.TrialContract.workspace(bad));
});
const inputs = [
  { name: 'cross-night', occupied_hours: 389.2, available_occupied_hours: 101.2, available_hours: 115.8, outside_available_hours: 288, utilization: 101.2 / 115.8 },
  { name: 'zero', occupied_hours: 8, available_occupied_hours: 0, available_hours: 0, outside_available_hours: 8, utilization: null },
  { name: 'unknown', occupied_hours: 8, available_occupied_hours: null, available_hours: null, outside_available_hours: null, utilization: null }
];
for (const values of inputs) {
  plan.projections.occupancy.resources.forEach(row => Object.assign(row, values));
  const before = JSON.stringify(plan), fmt = window.WorkbenchFormat;
  check(values.name + ' task detail', () => {
    const tree = render(window.PlanDetailsUI.TaskDetail, { data: plan, selected: { task, before: false } });
    const section = nodes(tree).find(node => node.type === 'section' && nodes(node).some(child => child.type === 'h3' && text(child) === '资源占用'));
    const facts = nodes(section).filter(node => node.type === window.PlanDetailsUI.Facts);
    assert.equal(facts.length, 2);
    for (const fact of facts) {
      const cells = Object.fromEntries(fact.props.items);
      assert.equal(cells['班表内占用'], values.available_occupied_hours === null ? '暂无数据' : fmt.hours(values.available_occupied_hours, 2));
      assert.equal(cells['可用时间'], values.available_hours === null ? '暂无数据' : fmt.hours(values.available_hours, 2));
      assert.equal(cells['班表外占用'], values.outside_available_hours === null ? '暂无数据' : fmt.hours(values.outside_available_hours, 2));
      assert.equal(cells['占用率'], values.utilization === null ? '暂无数据' : '87.39%');
      assert(!Object.hasOwn(cells, '已占时间'));
    }
  });
  check(values.name + ' plan load table', () => {
    const tree = render(window.PlanDetailsUI.ProjectionTables, { data: plan }, ['load', 0]);
    const headers = nodes(tree).filter(node => node.type === 'th').map(text);
    assert.equal(headers[2], '班表内占用（小时）'); assert.equal(headers[6], '班表外占用（小时）');
    const cells = nodes(nodes(tree).find(node => node.type === 'tbody')).filter(node => node.type === 'td').map(text);
    assert.equal(cells[2], fmt.number(values.available_occupied_hours, 2));
    assert.equal(cells[5], values.utilization === null ? '未知' : '87.39%');
    assert.equal(cells[6], fmt.number(values.outside_available_hours, 2));
  });
  check(values.name + ' trial results', () => {
    const value = clone(draft); value.capacity.resources.forEach(row => Object.assign(row, values));
    const original = JSON.stringify(value), tree = render(window.TrialResults.Results, { data: value });
    const table = nodes(tree).find(node => node.type === window.TrialControls.Table && node.props.label === '资源占用');
    const columns = Object.fromEntries(table.props.columns), row = value.capacity.resources[0], number = window.TrialControls.number;
    assert.equal(columns['班表内占用（小时）'](row), number(values.available_occupied_hours));
    assert.equal(columns['班表外占用（小时）'](row), number(values.outside_available_hours));
    assert.equal(columns['班表内占用率'](row), values.utilization === null ? '暂无数据' : '87.39%');
    assert(!Object.hasOwn(columns, '实际占用（小时）'));
    assert.equal(JSON.stringify(value), original);
  });
  assert.equal(JSON.stringify(plan), before);
}
console.log(JSON.stringify({ cases: checks.length, passed: checks, global_build: false, browser: false }));
