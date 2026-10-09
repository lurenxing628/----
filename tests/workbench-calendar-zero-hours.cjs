'use strict';
// No browser: 全局日历和个人日历编辑某天时，设成工作日却没有可排工时，表单里显示同一句提醒，不拦保存。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '..'), app = path.join(root, 'frontend/workbench/app');
const output = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'),
  sources: ['CalendarFields.jsx', 'OperatorCalendarPanel.jsx'].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })), check_combined: true });
let slots = [], index = 0;
const state = initial => {
  const at = index++;
  if (!(at in slots)) slots[at] = typeof initial === 'function' ? initial() : initial;
  return [slots[at], value => { slots[at] = typeof value === 'function' ? value(slots[at]) : value; }];
};
const React = { Fragment: 'Fragment', createElement: (type, props, ...children) => ({ type, props: { ...props, children } }), useState: state,
  useRef: value => state(() => ({ current: value }))[0], useEffect() {}, useLayoutEffect() {}, useId: () => 'calendar' };
const failure = message => Object.assign(new Error(message), { fields: [] });
const writeContext = { capabilities: { 'operator.calendar_upsert': true, 'operator.calendar_delete': true, 'operator.calendar_range_clear': true } };
let monthData = null;
const window = {
  APSResourceContract: { object: v => v !== null && typeof v === 'object' && !Array.isArray(v), own: (v, k) => Object.prototype.hasOwnProperty.call(v, k), failure, blocked: () => '' },
  APSResourceSession: { useQuery: () => ({ result: { data: monthData, warnings: [] }, loading: false, error: null, reload() {} }) },
  ResourceControls: { Button: 'Button', ErrorBox: 'ErrorBox', Field: 'Field', Issues: 'Issues', Modal: 'Modal' },
  WorkbenchGuards: { useDirtyGuard: () => 'owner', confirmLeave: async () => true },
  WorkbenchTerms: { personal_calendar: '个人日历' }, WorkbenchFormat: { hours: v => String(v) }, WorkPeriodFields: 'WorkPeriodFields'
};
const context = vm.createContext({ React, window, console });
for (const name of ['WorkPeriods.js', 'OperatorCalendarContract.js']) vm.runInContext(fs.readFileSync(path.join(app, name), 'utf8'), context);
output.outputs.forEach(row => vm.runInContext(row.code, context));
function expand(node) {
  if (Array.isArray(node)) return node.map(expand);
  if (!node || typeof node !== 'object') return node;
  if (typeof node.type === 'function') return expand(node.type(node.props));
  return { ...node, props: { ...node.props, children: expand(node.props.children) } };
}
function nodes(value) {
  if (Array.isArray(value)) return value.flatMap(nodes);
  if (!value || typeof value !== 'object') return [];
  return [value, ...nodes(value.props.children)];
}
const note = window.APSWorkPeriods.zeroHoursNote;
const notes = tree => nodes(tree).filter(node => node.type === 'Issues').flatMap(node => node.props.issues).filter(item => item === note);
// 与日历文件导入预检的提醒同一口径。
assert(note.startsWith('这一天是工作日，但可排工时是 0，排产时'), '页面提醒与文件导入提醒同一口径');
assert(fs.readFileSync(path.join(root, 'core/services/workbench/resource/calendar_files/files.py'), 'utf8').includes('这一天是工作日，但可排工时是 0，排产时'));

// 全局日历：分段时段全部移除或可排工时填 0 时提醒；休息日、有时段、有工时、工时未填不提醒。
const day = { type: 'work', hours: '8', eff: '100', allowNormal: 'yes', allowUrgent: 'yes', note: '', shiftStart: '08:00', shiftEnd: '', periods: null };
const fields = value => { slots = []; index = 0; return expand(window.CalendarFields.Fields({ value, onChange() {} })); };
assert.equal(notes(fields({ ...day, periods: [], hours: '0' })).length, 1, '工作日时段全部移除时提醒');
assert.equal(notes(fields({ ...day, hours: '0' })).length, 1, '工作日可排工时填 0 时提醒');
assert.equal(notes(fields(day)).length, 0, '有工时不提醒');
assert.equal(notes(fields({ ...day, hours: '' })).length, 0, '工时还没填时交给必填校验，不提醒');
assert.equal(notes(fields({ ...day, periods: [{ start: '08:00', end: '12:00', day_offset: 0 }], hours: '4' })).length, 0, '有工作时段不提醒');
assert.equal(notes(fields({ ...day, type: 'rest', periods: [], hours: '0' })).length, 0, '休息日不提醒');

// 个人日历：点一天，上班但工作时段全部移除时提醒；保存按钮照常可用。
const date = '2026-10-05', defaults = [{ start: '08:30', end: '11:50', day_offset: 0 }, { start: '13:30', end: '17:30', day_offset: 0 }];
const blank = { date, day: 5, weekday: 0, is_weekend: false, is_today: false, explicit: false, calendar_ref: null, default_periods: defaults,
  day_type: null, shift_start: null, shift_end: null, shift_hours: null, efficiency: null, allow_normal: null, allow_urgent: null, remark: null };
monthData = { days: [blank], cells: [blank], stats: { configured: 0, work_days: 0 }, write_context: writeContext, previous_month: null, next_month: null };
const command = { locked: false, phase: 'idle', error: null, result: null, reset: () => true, submit() {} };
const props = { adapter: { query() {} }, entity: { ref: 'a'.repeat(48), business_code: 'OP-1' }, source: 'production', command, onClose() {},
  refreshState: {}, onRefresh() {}, Feedback: 'Feedback' };
slots = [];
const panel = () => { index = 0; return expand(window.OperatorCalendarPanel(props)); };
(async () => {
  let tree = panel();
  await nodes(tree).find(node => node.props['data-operator-calendar-date'] === date).props.onClick();
  tree = panel();
  const periods = () => nodes(tree).find(node => node.type === 'WorkPeriodFields');
  assert.equal(periods().props.value.length, 2, '没单独设置的一天默认带工作时段');
  assert.equal(notes(tree).length, 0, '有工作时段不提醒');
  periods().props.onChange([]);
  tree = panel();
  assert.equal(notes(tree).length, 1, '上班但工作时段全部移除时提醒');
  const save = nodes(tree).find(node => node.type === 'Button' && node.props.children.includes('保存这一天'));
  assert.equal(save.props.disabled, false, '提醒不拦保存');
  nodes(tree).find(node => node.type === 'button' && node.props['aria-pressed'] === false && node.props.children.includes('休息')).props.onClick();
  tree = panel();
  assert.equal(notes(tree).length, 0, '休息不提醒');
  console.log('calendar zero-hour workday note shows on both calendar forms without blocking save');
})().catch(error => { console.error(error); process.exit(1); });
