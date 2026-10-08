'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: [{ path: 'ResourceRail.jsx', code: fs.readFileSync(path.join(app, 'ResourceRail.jsx'), 'utf8') }] }).outputs[0].code;
const nodes = Object.fromEntries([
  ['process', '工艺', '项'], ['material', '物料', '条'], ['op_int', '自制工种', '个'], ['machine', '设备', '台'],
  ['operator', '人员', '人'], ['op_ext', '外协工种', '个'], ['supplier', '供应商', '家']
].map(([key, label, unit]) => [key, { label, unit, icon: key }]));
function runtime(storage = new Map()) {
  let choice;
  const React = { Fragment: 'fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }),
    useState(initial) { if (!choice) choice = initial(); return [choice, value => { choice = value; }]; } };
  const context = vm.createContext({ React, sessionStorage: { getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value) },
    window: { APSResourceContract: { nodes, message: error => error.message }, ResourceControls: {
      Button: props => React.createElement('button', props, props.children), Icon: () => null,
      MetricValue: props => props.pending ? React.createElement('span', { 'data-pending': true }) : props.children
    } } });
  vm.runInContext(fs.readFileSync(path.join(app, 'WorkbenchFormat.js'), 'utf8'), context);
  vm.runInContext(built, context);
  return props => expand(context.window.ResourceRail(props));
}
function expand(node) {
  if (Array.isArray(node)) return node.flatMap(item => { const value = expand(item); return Array.isArray(value) ? value : [value]; });
  if (!node || typeof node !== 'object') return node;
  if (typeof node.type === 'function') return expand(node.type(node.props));
  return { ...node, props: { ...node.props, children: expand(node.props.children) } };
}
function all(node) {
  if (Array.isArray(node)) return node.flatMap(all);
  return node && typeof node === 'object' ? [node, ...all(node.props.children)] : [];
}
const find = (node, predicate) => all(node).find(predicate);
function text(node) {
  if (Array.isArray(node)) return node.map(text).join('');
  return node && typeof node === 'object' ? text(node.props.children) : node == null || node === false ? '' : String(node);
}
const hasClass = (node, name) => (node.props.className || '').split(' ').includes(name);
function fixture() {
  const items = Object.fromEntries(Object.keys(nodes).map(key => [key, { status: 'recorded', counts: { total: 3, active: 3 }, issues: [] }]));
  items.process = { status: 'pending', counts: { total: 4, route: 0, source: 4, hours: 0, ready: 0, legacy: 4, managed: 0,
    legacy_route_present: 4, route_confirmed: 0, source_confirmed: 0, hours_confirmed: 0 }, issues: [] };
  items.material.counts = { total: 0 };
  items.op_int.counts = { total: 3, active: 3, without_machines: 0, available_operators: 3 };
  items.op_ext.counts = { total: 1, active: 1, merge_mode_unset: 1, available_suppliers: 1 };
  const days = Array.from({ length: 7 }, (_, index) => ({ date: '2026-10-' + String(5 + index).padStart(2, '0'), weekday: index,
    source: 'service_default', status: 'known', explicit: false, issues: [], effective: { is_rest: index >= 5,
      rest_reason: index === 5 ? 'priorities_disabled' : index === 6 ? 'zero_hours' : null, effective_hours: index >= 5 ? 0 : 7.3,
      window_start: '2026-10-05T08:00:00', window_end: '2026-10-05T16:00:00', hours: 8, efficiency: 1,
      allow_normal: index < 5, allow_urgent: index < 5, crosses_midnight: false } }));
  const calendar = { days, week_start: '2026-10-05', week_end: '2026-10-11', factory_today: '2026-10-08', basis: '全局班次按起始日期归到那一天。',
    standard_hours: { status: 'known', value: 7.3 }, holiday_default_efficiency: { status: 'known', value: 0.8, basis: '假期未填写效率时使用此值。', issues: [] },
    stats: { work_days: 5, rest_days: 2, configured_days: 0, default_days: 7, effective_hours: 36.5,
      normal_effective_hours: 36.5, urgent_effective_hours: 36.5, issues: [], unavailable_days: 0 } };
  const counts = Object.fromEntries(Object.entries(items).map(([key, item]) => [key, { total: item.counts.total }]));
  counts.summary = { loading: false, error: null, data: { readiness: { items }, calendar } };
  return { node: 'material', counts, onNode() {}, onNavigate() {} };
}

// A fresh session opens the preparation chain. Manual choices survive node switches and remounts.
const storage = new Map(), render = runtime(storage), props = fixture();
let tree = render(props);
assert.equal(tree.props['data-collapsed'], 'false');
assert(!text(tree).includes('只读汇总'));
assert(text(tree).includes('待归属 4'));
// Preparation keeps one reading order, with equipment and people as parallel targets of the internal work type.
assert(text(tree).includes('工艺与物料'));
assert(text(tree).includes('加工资源'));
assert(text(tree).includes('按工时排产'));
assert(text(tree).includes('按自然日周期'));
const internal = find(tree, node => node.props['data-resource-source'] === 'op_int');
const external = find(tree, node => node.props['data-resource-source'] === 'op_ext');
assert.equal(internal.props['data-resource-targets'], 'machine operator');
assert.equal(external.props['data-resource-targets'], 'supplier');
assert.deepEqual(all(find(internal, node => hasClass(node, 'rail-branch-source'))).filter(node => node.props['data-rail-node']).map(node => node.props['data-rail-node']), ['op_int']);
assert.deepEqual(all(find(internal, node => hasClass(node, 'rail-branch-targets'))).filter(node => node.props['data-rail-node']).map(node => node.props['data-rail-node']), ['machine', 'operator']);
assert(text(internal).includes('未关联设备 0'));
assert(text(internal).includes('匹配人员 3'));
assert(text(external).includes('匹配供应商 1'));
assert(!text(tree).includes('匹配设备'));
find(tree, node => hasClass(node, 'rail-toggle')).props.onClick();
tree = render({ ...props, node: 'machine' });
assert.equal(tree.props['data-collapsed'], 'true');
const remount = runtime(storage);
tree = remount(props);
assert.equal(tree.props['data-collapsed'], 'true');
find(tree, node => hasClass(node, 'rail-toggle')).props.onClick();
tree = remount(props);
assert.equal(tree.props['data-collapsed'], 'false');
assert.equal(storage.get('aps_resource_rail_collapsed'), 'false');

// Each day has a compact unit-free value, while rest, prohibited scheduling and unknown remain different facts.
let calendar = find(tree, node => hasClass(node, 'hb-cal-block'));
const cells = all(calendar).filter(node => node.props['data-calendar-date']);
assert.equal(cells.length, 7);
assert.equal(text(find(cells[0], node => hasClass(node, 'rail-day-value'))), '7.3');
assert.equal(text(find(cells[5], node => hasClass(node, 'rail-day-value'))), '禁排');
assert.equal(text(find(cells[6], node => hasClass(node, 'rail-day-value'))), '休息');
assert(!text(find(calendar, node => hasClass(node, 'hb-cal-strip'))).includes('默认'));
assert(!text(find(calendar, node => hasClass(node, 'hb-cal-strip'))).includes('小时'));
assert(text(calendar).includes('每日有效工时（小时）'));
assert(text(calendar).includes('自制 · 全局'));
assert(text(calendar).includes('本周全部按默认规则'));
assert(!text(calendar).includes('普通件'));
props.counts.summary.data.calendar.stats.urgent_effective_hours = 0;
tree = remount(props); calendar = find(tree, node => hasClass(node, 'hb-cal-block'));
assert(text(calendar).includes('普通件 36.5 小时 · 急件 0.0 小时'));

// Business failures remain visible above both expanded and collapsed navigation, including the actual error.
const failed = fixture();
failed.counts.summary.data.readiness.items.process.issues.push({ message: '工艺确认记录读取失败，请联系维护人员核对。' });
failed.counts.summary.data.calendar.days[0].effective = null;
failed.counts.summary.data.calendar.days[0].status = 'unavailable';
failed.counts.summary.data.calendar.days[0].issues.push({ message: '班次时长无效。' });
Object.assign(failed.counts.summary.data.calendar.stats, { work_days: null, rest_days: null, effective_hours: null, normal_effective_hours: null,
  urgent_effective_hours: null, unavailable_days: 1 });
tree = remount(failed);
assert.equal(text(find(tree, node => node.props['data-calendar-date'] === '2026-10-05')).includes('未知'), true);
assert.equal(text(find(tree, node => node.props['data-calendar-week-hours'])), '本周有效 暂无数据');
find(tree, node => hasClass(node, 'rail-toggle')).props.onClick(); tree = remount(failed);
const notices = find(tree, node => hasClass(node, 'rail-notices'));
assert(text(notices).includes('工艺确认记录读取失败'));
assert(text(notices).includes('2026-10-05：班次时长无效。'));
failed.counts.summary.error = { message: '本机数据库无法读取。' };
assert(text(find(remount(failed), node => hasClass(node, 'rail-notices'))).includes('本机数据库无法读取。'));

const loading = fixture(); loading.counts.summary = { loading: true };
tree = runtime()(loading);
assert(text(tree).includes('正在读取…'));
assert(!text(tree).includes('未知'));
assert(!text(tree).includes('暂无数据'));

const uncertain = fixture();
uncertain.counts.summary.data.readiness.items.op_int.counts.available_operators = null;
uncertain.counts.summary.data.readiness.items.op_ext.counts.available_suppliers = 0;
tree = runtime()(uncertain);
assert(text(find(tree, node => node.props['data-resource-source'] === 'op_int')).includes('匹配人员 未知'));
assert(text(find(tree, node => node.props['data-resource-source'] === 'op_ext')).includes('匹配供应商 0'));

console.log('resource rail presentation contract: passed');
