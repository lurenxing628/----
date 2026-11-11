'use strict';
// No browser: 全局日历、批量维护、个人日历与默认工作时间的零工时提醒与时段错误唯一归属契约。
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '..'), app = path.join(root, 'frontend/workbench/app');

const jsSources = [
  'WorkbenchFormat.js', 'WorkbenchTerms.js', 'shared/network/transport.js', 'resource-contract.js',
  'WorkPeriods.js', 'CalendarContract.js', 'OperatorCalendarContract.js'
];
const jsxSources = [
  'WorkbenchReferences.jsx',
  'ResourceControls.jsx',
  'WorkPeriodFields.jsx',
  'OperatorCalendarPanel.jsx',
  'ResourceForms.jsx',
  'CalendarFields.jsx',
  'CalendarDayDialog.jsx',
  'CalendarDefaultsDialog.jsx',
  'CalendarRangeDialog.jsx'
];
const output = compile({
  sources: [...jsSources, ...jsxSources].map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })),
  check_combined: true
});

const document = {
  body: { style: {} },
  documentElement: { style: {}, setAttribute() {} },
  activeElement: null,
  addEventListener() {},
  removeEventListener() {}
};
const context = vm.createContext({
  console, document, URL, URLSearchParams, Map, Set, WeakMap, WeakSet, Date,
  setTimeout, clearTimeout, queueMicrotask, AbortController, DOMException, FormData, Blob, Headers, Response
});
context.window = context;
context.self = context;
context.location = { origin: 'http://localhost', href: 'http://localhost/workbench' };
context.addEventListener = () => {};
context.removeEventListener = () => {};
context.dispatchEvent = () => {};
context.__wbStubs = {
  'shared/ui/icons.jsx': {
    Ico: ({ name }) => context.React.createElement('svg', { 'data-ico': name, 'aria-hidden': true }),
    SMIcon: ({ name }) => context.React.createElement('svg', { 'data-sm-icon': name, 'aria-hidden': true }),
    TransferIcon: ({ kind }) => context.React.createElement('svg', { 'data-transfer': kind, 'aria-hidden': true }),
  },
  'FieldReportIcons.js': { iconNodes: {} },
};

vm.runInContext(fs.readFileSync(path.join(root, 'static/workbench/vendor/react-18.3.1.production.min.js'), 'utf8'), context);
const realReact = context.React;
const providerType = realReact.createContext(null).Provider.$$typeof;

let frames = new Map(), callCounts = new Map(), contextValues = new Map(), idCounter = 0;
let activePath = [];
function resetHooks() {
  frames = new Map();
  resetRenderPass();
}
function resetRenderPass() {
  callCounts = new Map();
  contextValues = new Map();
  idCounter = 0;
  activePath = [];
}
function currentFrameKey() {
  return activePath.join('/');
}
context.React = Object.assign({}, realReact, {
  useState(initial) {
    const key = currentFrameKey();
    let frame = frames.get(key);
    if (!frame) frames.set(key, frame = { slots: [], cursor: 0 });
    const at = frame.cursor++;
    if (!(at in frame.slots)) frame.slots[at] = typeof initial === 'function' ? initial() : initial;
    return [frame.slots[at], next => { frame.slots[at] = typeof next === 'function' ? next(frame.slots[at]) : next; }];
  },
  useRef(initial) {
    return context.React.useState(() => ({ current: initial }))[0];
  },
  useMemo: fn => fn(),
  useCallback: fn => fn,
  useId: () => 'cal-' + (++idCounter),
  useContext: ctx => contextValues.has(ctx) ? contextValues.get(ctx) : ctx._currentValue,
  useEffect() {},
  useLayoutEffect() {}
});

const compiledMap = new Map(output.outputs.map(row => [row.path, row.code]));
for (const name of jsSources) {
  vm.runInContext(compiledMap.get(name), context, { filename: name });
}

let queryResult = { result: null, loading: false, error: null, reload() {} };
context.__wbRuntime.setStubs({
  'shared/session/query.js': { useQuery: () => queryResult },
  'WorkbenchGuards.js': {
    useDirtyGuard: () => 'guard-owner',
    confirmLeave: async () => true
  },
  'WorkbenchControls.jsx': {},
});
jsxSources.forEach(name => vm.runInContext(compiledMap.get(name), context, { filename: name }));
const getMod = rel => context.__wbRuntime.getModule(rel);
const w = {
  APSWorkPeriods: getMod('WorkPeriods.js'),
  CalendarFields: getMod('CalendarFields.jsx'),
  APSCalendarContract: getMod('CalendarContract.js'),
  APSOperatorCalendar: getMod('OperatorCalendarContract.js'),
  APSWorkbenchTransport: getMod('shared/network/transport.js'),
  WorkPeriodFields: getMod('WorkPeriodFields.jsx'),
  CalendarDayDialog: getMod('CalendarDayDialog.jsx'),
  CalendarRangeDialog: getMod('CalendarRangeDialog.jsx'),
  OperatorCalendarPanel: getMod('OperatorCalendarPanel.jsx'),
  ResourceForms: getMod('ResourceForms.jsx'),
  CalendarDefaultsDialog: getMod('CalendarDefaultsDialog.jsx'),
  APSResourceContract: getMod('resource-contract.js'),
};

function expand(element) {
  if (element === null || element === undefined || typeof element === 'boolean') return null;
  if (typeof element === 'string' || typeof element === 'number') return element;
  if (Array.isArray(element)) return element.map(expand);
  assert(realReact.isValidElement(element), 'Expected valid React element');
  if (element.type === realReact.Fragment) return expand(element.props.children);
  if (element.type && element.type.$$typeof === providerType) {
    const ctx = element.type._context, had = contextValues.has(ctx), prev = contextValues.get(ctx);
    contextValues.set(ctx, element.props.value);
    try { return expand(element.props.children); }
    finally { if (had) contextValues.set(ctx, prev); else contextValues.delete(ctx); }
  }
  if (typeof element.type === 'function') {
    const baseName = element.type.name || 'Anon';
    const seen = (callCounts.get(baseName) || 0) + 1;
    callCounts.set(baseName, seen);
    const token = baseName + '#' + seen;
    activePath.push(token);
    const frame = frames.get(currentFrameKey());
    if (frame) frame.cursor = 0;
    try { return expand(element.type(element.props)); }
    finally { activePath.pop(); }
  }
  if (element.ref && typeof element.ref === 'object') {
    element.ref.current = { querySelectorAll: () => [], contains: () => false, focus() {} };
  }
  return { type: element.type, props: element.props, children: expand(element.props.children) };
}
function render(Component, props) {
  resetRenderPass();
  return expand(realReact.createElement(Component, props));
}
function nodes(tree) {
  if (tree === null || tree === undefined) return [];
  if (Array.isArray(tree)) return tree.flatMap(nodes);
  if (typeof tree !== 'object') return [];
  return [tree, ...nodes(tree.children)];
}
function visible(node) {
  if (node === null || node === undefined || typeof node === 'boolean') return '';
  if (Array.isArray(node)) return node.map(visible).join('');
  if (typeof node !== 'object') return String(node);
  const p = node.props || {};
  if (p.hidden || p['aria-hidden'] === true || p['aria-hidden'] === 'true'
      || /\bwb-visually-hidden\b/.test(p.className || '')
      || p.style && (p.style.display === 'none' || p.style.visibility === 'hidden')) return '';
  if (node.type === 'details' && !p.open) {
    const flat = Array.isArray(node.children) ? node.children.flat(Infinity) : [node.children];
    return visible(flat.find(child => child && child.type === 'summary'));
  }
  return visible(node.children);
}
const countVisible = (tree, message) => visible(tree).split(message).length - 1;
const alerts = tree => nodes(tree).filter(node => node.props && node.props.role === 'alert');
const fieldAlerts = tree => alerts(tree).filter(node => /\bwb-field-error\b/.test(node.props.className || ''));
const timeInputs = tree => nodes(tree).filter(node => node.type === 'input' && node.props.type === 'time');

const note = w.APSWorkPeriods.zeroHoursNote;
const notes = tree => nodes(tree).filter(node => /\bwb-issues\b/.test(node.props && node.props.className || ''))
  .filter(node => visible(node).includes(note));

assert.equal(w.APSWorkPeriods.defaults, undefined, '前端不维护静态默认工作时段');

// 全局日历：工作日时段全部移除时提醒；有时段或休息日不提醒。
const baseDayDraft = { type: 'work', eff: '100', allowNormal: 'yes', allowUrgent: 'yes', note: '',
  periods: [{ start: '08:00', end: '16:00', day_offset: 0 }] };
const renderFields = (value, error = null) => { resetHooks(); return render(w.CalendarFields.Fields, { value, error, onChange() {} }); };
assert.equal(notes(renderFields({ ...baseDayDraft, periods: [] })).length, 1, '工作日时段全部移除时提醒');
assert.equal(notes(renderFields(baseDayDraft)).length, 0, '有工作时段不提醒');
assert.equal(notes(renderFields({ ...baseDayDraft, periods: [{ start: '08:00', end: '12:00', day_offset: 0 }] })).length, 0, '单段工作时段不提醒');
assert.equal(notes(renderFields({ ...baseDayDraft, type: 'rest', periods: [] })).length, 0, '休息日不提醒');

// 批量维护与单日草稿：自定义默认时段（06:00-14:00）贯穿新建草稿、休息/工作切换与 input() 输出。
const factoryDefault = [{ start: '06:00', end: '14:00', day_offset: 0 }];
let rangeDraft = w.APSCalendarContract.draft(factoryDefault);
assert.equal(JSON.stringify(rangeDraft.periods), JSON.stringify(factoryDefault));
assert.equal(JSON.stringify(rangeDraft.defaultPeriods), JSON.stringify(factoryDefault));
rangeDraft = w.APSCalendarContract.switchType({ ...rangeDraft, periods: [] }, 'rest');
rangeDraft = w.APSCalendarContract.switchType(rangeDraft, 'work');
assert.equal(JSON.stringify(rangeDraft.periods), JSON.stringify(factoryDefault), '批量维护从休息切回工作日时恢复工厂默认时段');
assert.equal(JSON.stringify(w.APSCalendarContract.input(rangeDraft)), JSON.stringify({
  type: 'work', periods: factoryDefault, note: null, eff: 100, allowNormal: 'yes', allowUrgent: 'yes'
}));

const calendarWriteContext = {
  write_token: 'tok-cal',
  capabilities: { 'calendar.upsert': true, 'calendar.delete': true, 'calendar.confirm': true, 'calendar.defaults': true },
  blocked_reasons: []
};
const calendarDayDto = d => ({
  date: '2026-10-' + String(d).padStart(2, '0'), day: d, weekday: (d + 2) % 7, is_weekend: (d + 2) % 7 >= 5, is_today: false,
  explicit: false, calendar_ref: null, entity: null, stored: null, default_periods: factoryDefault,
  write_context: calendarWriteContext,
  fields: { type: 'work', hours: 8, eff: 100, allowNormal: 'yes', allowUrgent: 'yes', note: null, periods: factoryDefault },
  effective: { is_working: true, window_start: '2026-10-01T06:00:00', window_end: '2026-10-01T14:00:00', periods: factoryDefault }
});
const urgentOnlyDay = {
  ...calendarDayDto(1),
  explicit: true,
  calendar_ref: 'b'.repeat(48),
  entity: { ref: 'b'.repeat(48) },
  stored: { day_type: 'workday', efficiency: 1, allow_normal: 'no', allow_urgent: 'yes' },
  fields: { type: 'work', hours: 8, eff: 100, allowNormal: 'no', allowUrgent: 'yes', note: null, periods: factoryDefault }
};
let urgentDraft = w.APSCalendarContract.draft(urgentOnlyDay);
urgentDraft = w.APSCalendarContract.switchType(urgentDraft, 'rest');
urgentDraft = w.APSCalendarContract.switchType(urgentDraft, 'work');
assert.equal(urgentDraft.allowNormal, 'no', '已有仅急件工作日往返切换后保留普通件限制');
assert.equal(urgentDraft.allowUrgent, 'yes');
assert.equal(JSON.stringify(w.APSCalendarContract.input(urgentDraft, urgentOnlyDay)), '{}');
const restFromBlankEff = w.APSCalendarContract.switchType({ ...w.APSCalendarContract.draft(urgentOnlyDay), eff: '' }, 'rest');
assert.equal(JSON.stringify(w.APSCalendarContract.input(restFromBlankEff, urgentOnlyDay)), JSON.stringify({
  type: 'rest', periods: []
}));
assert.equal(JSON.stringify(w.APSCalendarContract.input(restFromBlankEff)), JSON.stringify({
  type: 'rest', periods: [], note: null
}));

// 休息日改工作日：即使工作时段和原来一样也必须提交，全部移除就是明确的零工时；后端不替它沿用。
const restDay = {
  ...urgentOnlyDay,
  stored: { day_type: 'holiday', efficiency: 1, allow_normal: 'no', allow_urgent: 'no' },
  fields: { type: 'rest', hours: 0, eff: 100, allowNormal: 'no', allowUrgent: 'no', note: null, periods: [] }
};
const restToWork = w.APSCalendarContract.switchType(w.APSCalendarContract.draft(restDay), 'work');
assert.equal(JSON.stringify(restToWork.periods), JSON.stringify(factoryDefault), '休息日切回工作日先填默认时段');
assert.equal(JSON.stringify(w.APSCalendarContract.input(restToWork, restDay).periods), JSON.stringify(factoryDefault));
assert.equal(JSON.stringify(w.APSCalendarContract.input({ ...restToWork, periods: [] }, restDay).periods), '[]', '全部移除后明确提交空时段');
const stoppedHoliday = { ...restDay, fields: { ...restDay.fields, periods: factoryDefault } };
assert.equal(JSON.stringify(w.APSCalendarContract.input(
  w.APSCalendarContract.switchType(w.APSCalendarContract.draft(stoppedHoliday), 'work'), stoppedHoliday).periods),
JSON.stringify(factoryDefault), '原有时段不变也随类型一起提交');

const validCalendarMonth = {
  data: {
    year: 2026, month: 6, time_basis: 'factory_local', default_periods: factoryDefault,
    days: Array.from({ length: 30 }, (_, i) => ({
      ...calendarDayDto(i + 1),
      date: '2026-06-' + String(i + 1).padStart(2, '0'),
      day: i + 1,
      weekday: i % 7,
      is_weekend: i % 7 >= 5
    })),
    cells: Array.from({ length: 30 }, (_, i) => ({
      ...calendarDayDto(i + 1),
      date: '2026-06-' + String(i + 1).padStart(2, '0'),
      day: i + 1,
      weekday: i % 7,
      is_weekend: i % 7 >= 5
    })).concat([null, null, null, null, null]),
    stats: { work_days: 22, configured: 0, overrides: 0, weekend_rest: 8 }
  }
};
assert.equal(w.APSCalendarContract.month(validCalendarMonth, 2026, 6), validCalendarMonth);

// 个人日历：自定义默认时段贯穿草稿、切换与提交。
const opWriteContext = {
  write_token: 'tok-op',
  capabilities: { 'operator.calendar_upsert': true, 'operator.calendar_delete': true, 'operator.calendar_range_clear': true },
  blocked_reasons: []
};
const date = '2026-10-05', defaults = [{ start: '08:30', end: '11:50', day_offset: 0 }, { start: '13:30', end: '17:30', day_offset: 0 }];
const blank = { date, day: 5, weekday: 0, is_weekend: false, is_today: false, explicit: false, calendar_ref: null, default_periods: defaults,
  day_type: null, efficiency: null, allow_normal: null, allow_urgent: null, remark: null };
const customBlank = { ...blank, default_periods: factoryDefault };
let operatorDraft = w.APSOperatorCalendar.draftOf(customBlank);
assert.equal(JSON.stringify(operatorDraft.periods), JSON.stringify(factoryDefault));
operatorDraft = w.APSOperatorCalendar.switchType(customBlank, { ...operatorDraft, periods: [] }, 'rest');
operatorDraft = w.APSOperatorCalendar.switchType(customBlank, operatorDraft, 'work');
assert.equal(JSON.stringify(operatorDraft.periods), JSON.stringify(factoryDefault));
assert.equal(JSON.stringify(w.APSOperatorCalendar.input(operatorDraft, customBlank)), JSON.stringify({
  type: 'work', allowNormal: 'yes', allowUrgent: 'yes', eff: 100, periods: factoryDefault, note: null
}));
const opRestFromBlankEff = w.APSOperatorCalendar.switchType(customBlank, { ...operatorDraft, eff: '' }, 'rest');
assert.equal(JSON.stringify(w.APSOperatorCalendar.input(opRestFromBlankEff, customBlank)), JSON.stringify({
  type: 'rest', allowNormal: 'no', allowUrgent: 'no', periods: [], note: null
}));
const explicitDay = { ...blank, explicit: true, calendar_ref: 'c'.repeat(48), day_type: 'workday', efficiency: 1,
  allow_normal: 'yes', allow_urgent: 'yes', periods: defaults };
const explicitDraft = w.APSOperatorCalendar.draftOf(explicitDay);
assert.equal(JSON.stringify(w.APSOperatorCalendar.input({ ...explicitDraft, note: '   ' }, explicitDay)), JSON.stringify({
  type: 'work', allowNormal: 'yes', allowUrgent: 'yes', periods: defaults, note: null
}), '已单独设置日期效率未改动时不重复带 eff，空白备注归一为 null');
assert.equal(JSON.stringify(w.APSOperatorCalendar.input({ ...explicitDraft, eff: ' 125 ', note: ' 夜班 ' }, explicitDay)), JSON.stringify({
  type: 'work', allowNormal: 'yes', allowUrgent: 'yes', eff: 125, periods: defaults, note: '夜班'
}));
assert.equal(w.APSOperatorCalendar.tag(explicitDay).tone, 'cfg');
assert.equal(w.APSOperatorCalendar.tag({ ...explicitDay, periods: [] }).tone, 'rest', '零工时工作日显示休息');
assert.equal(w.APSOperatorCalendar.tag({ ...explicitDay, allow_normal: 'no', allow_urgent: 'no' }).tone, 'rest');
const ref = 'a'.repeat(48);
const validOperatorMonth = { data: { year: 2026, month: 10, operator_ref: ref, days: [blank], cells: [blank, null, null, null, null, null, null],
  stats: { configured: 0, work_days: 0 }, write_context: opWriteContext, previous_month: null, next_month: null } };
assert.equal(w.APSOperatorCalendar.month(validOperatorMonth, { year: 2026, month: 10, ref }), validOperatorMonth);

const overlapPeriods = [{ start: '08:00', end: '12:00', day_offset: 0 }, { start: '11:00', end: '15:00', day_offset: 0 }];
const incompletePeriods = [{ start: '08:00', end: '', day_offset: 0 }];
const overlapMessage = '工作时段应按时间先后填写，不能重叠。';
const firstDayOffsetMessage = '首段须从当天开始。';
const incompleteMessage = '请补齐每段开始和结束时刻。';
const emptyDefaultMessage = '至少填写一个工作时段。';
const restToWorkMessage = '10-01 原来是假期或休息日，改成工作日时请填写工作时段。';
const serverPeriodsRejection = (fieldPath, message = restToWorkMessage) => w.APSWorkbenchTransport.failure({
  ok: false,
  committed: false,
  error: {
    code: 'invalid_input',
    message,
    fields: [{ path: fieldPath, message }],
    retryable: false,
    request_ref: '1'.repeat(32)
  }
}, 422);
const makeCommand = (overrides = {}) => ({
  locked: false, phase: 'idle', stale: false, error: null, result: null,
  reset: () => true, clearRejection: () => false, async submit() {},
  ...overrides
});
const findButton = (tree, label) => nodes(tree).find(node => node.type === 'button' && visible(node).includes(label));
const clickButton = (tree, label) => findButton(tree, label).props.onClick({ currentTarget: {}, preventDefault() {} });
const periodSelects = tree => nodes(tree).filter(node => node.type === 'select');

// 未传 path 的 WorkPeriodFields（如班次档轮换表）不认领表单错误，保持实时灰字提示不变。
resetHooks();
const unpathedTree = render(w.WorkPeriodFields, {
  value: overlapPeriods,
  disabled: false,
  onChange() {},
  error: serverPeriodsRejection('fields.periods')
});
assert.equal(fieldAlerts(unpathedTree).length, 0, '未传 path 的时段组件不认领字段错误');
assert.equal(countVisible(unpathedTree, overlapMessage), 1, '未传 path 时保留实时灰字校验提示');

(async () => {
  // 1. CalendarDayDialog：客户端重叠报错只出现 1 次且带 role="alert"；服务端 422 空时段报错完整可见无空红框。
  resetHooks();
  let dayCmd = makeCommand();
  const renderDay = () => render(w.CalendarDayDialog, {
    adapter: { query() {} }, day: restDay, source: 'production', command: dayCmd, onClose() {}, refreshState: {}, onRefresh() {}
  });
  let tree = renderDay();
  clickButton(tree, '工作日');
  tree = renderDay();
  assert.equal(periodSelects(tree).length, 1);
  assert.equal(periodSelects(tree)[0].props.disabled, true, '常规首段（day_offset: 0）开始日期下拉锁定为当天');
  // 把起止时间改成重叠时段：未点保存前只显示实时灰字提示，不弹 alert。
  clickButton(tree, '新增工作时段');
  tree = renderDay();
  assert.equal(periodSelects(tree)[0].props.disabled, true);
  assert.equal(periodSelects(tree)[1].props.disabled, false, '非首段开始日期下拉可切换当天/次日');
  let times = timeInputs(tree);
  times[0].props.onChange({ target: { value: '08:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[1].props.onChange({ target: { value: '12:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[2].props.onChange({ target: { value: '11:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[3].props.onChange({ target: { value: '15:00' } });
  tree = renderDay();
  assert.equal(fieldAlerts(tree).length, 0, '未提交前不触发 role="alert"');
  assert.equal(countVisible(tree, overlapMessage), 1, '未提交前显示实时灰字提示');

  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderDay();
  assert.equal(fieldAlerts(tree).length, 1, '客户端时段错误提交后渲染 role="alert"');
  assert.equal(visible(fieldAlerts(tree)[0]), overlapMessage);
  assert.equal(countVisible(tree, overlapMessage), 1, 'CalendarDayDialog 客户端时段错误只出现 1 次');
  assert.equal(periodSelects(tree)[0].props['aria-invalid'], undefined, '常规当天首段下拉不抢占 aria-invalid');
  assert(timeInputs(tree).every(input => input.props['aria-invalid'] === true), '时段输入框标记 aria-invalid');

  // 两段跨日（22:00-00:00 offset=0 + 01:00-03:00 offset=1）移除第 1 段后：
  // 新首段保留 day_offset === 1（不静默篡改），实时提示「首段须从当天开始。」，下拉解锁供用户一键切回「当天」后恢复锁定。
  times = timeInputs(tree);
  times[0].props.onChange({ target: { value: '22:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[1].props.onChange({ target: { value: '00:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[2].props.onChange({ target: { value: '01:00' } });
  tree = renderDay(); times = timeInputs(tree);
  times[3].props.onChange({ target: { value: '03:00' } });
  tree = renderDay();
  periodSelects(tree)[1].props.onChange({ target: { value: '1' } });
  tree = renderDay();
  assert.equal(countVisible(tree, '实际工作 4 小时；时段之间不排产。'), 1, '两段跨日时段校验通过');
  assert.equal(periodSelects(tree)[0].props.disabled, true);
  assert.equal(periodSelects(tree)[1].props.disabled, false);

  clickButton(tree, '移除第 1 段');
  tree = renderDay();
  assert.equal(periodSelects(tree).length, 1);
  assert.equal(periodSelects(tree)[0].props.value, 1, '移除跨日首段后新首段保留 day_offset === 1，不静默篡改');
  assert.equal(periodSelects(tree)[0].props.disabled, false, 'day_offset !== 0 的首段开始日期下拉保持可操作');
  assert.equal(countVisible(tree, firstDayOffsetMessage), 1, '实时灰字提示首段须从当天开始');

  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderDay();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), firstDayOffsetMessage);
  assert.equal(periodSelects(tree)[0].props['aria-invalid'], true, '提交报错时次日首段下拉挂 aria-invalid 供 focusFirstInvalid 聚焦');
  assert.equal(periodSelects(tree)[0].props['aria-describedby'], fieldAlerts(tree)[0].props.id);
  const firstInvalidControl = nodes(tree).find(node => ['select', 'input'].includes(node.type) && !node.props.disabled && node.props['aria-invalid'] === true);
  assert.equal(firstInvalidControl, periodSelects(tree)[0], 'focusFirstInvalid 首个可交互无效控件直指需修正的首段日期下拉');

  periodSelects(tree)[0].props.onChange({ target: { value: '0' } });
  tree = renderDay();
  assert.equal(fieldAlerts(tree).length, 0);
  assert.equal(countVisible(tree, firstDayOffsetMessage), 0, '切回当天后错误消除');
  assert.equal(countVisible(tree, '实际工作 2 小时；时段之间不排产。'), 1, '切回当天后校验通过');
  assert.equal(periodSelects(tree)[0].props.value, 0);
  assert.equal(periodSelects(tree)[0].props.disabled, true, '切回当天后首段开始日期下拉重新锁定');
  assert.equal(periodSelects(tree)[0].props['aria-invalid'], undefined);

  // 节假日转工作日且时段全部移除（periods=[]），提交后后端返回 422 input.fields.periods。
  while (findButton(tree, '移除第 1 段')) {
    findButton(tree, '移除第 1 段').props.onClick({ currentTarget: {} });
    tree = renderDay();
  }
  assert.equal(notes(tree).length, 1, '空时段工作日显示零工时提醒');
  dayCmd = makeCommand({
    async submit() { dayCmd = { ...dayCmd, phase: 'rejected', error: serverPeriodsRejection('input.fields.periods') }; }
  });
  tree = renderDay();
  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderDay();
  assert.equal(fieldAlerts(tree).length, 1, '后端 422 fields.periods 由 WorkPeriodFields 渲染 role="alert"');
  assert.equal(visible(fieldAlerts(tree)[0]), restToWorkMessage);
  assert.equal(countVisible(tree, restToWorkMessage), 1, 'CalendarDayDialog 后端 422 空时段报错完整可见且只出现 1 次');

  // 2. CalendarRangeDialog：客户端漏填报错与服务端预检/命令 422 fields.periods 报错唯一呈现。
  resetHooks();
  let previewError = null, rangeCmd = makeCommand();
  const renderRange = () => render(w.CalendarRangeDialog, {
    adapter: { async preview() { throw previewError; } },
    month: { year: 2026, month: 10 },
    defaultPeriods: factoryDefault,
    source: 'production',
    command: rangeCmd,
    onClose() {},
    refreshState: {},
    onRefresh() {}
  });
  tree = renderRange();
  findButton(tree, '新增工作时段').props.onClick({ currentTarget: {} });
  tree = renderRange();
  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderRange();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), incompleteMessage);
  assert.equal(countVisible(tree, incompleteMessage), 1, 'CalendarRangeDialog 客户端漏填时段错误只出现 1 次');
  assert(timeInputs(tree).every(input => input.props['aria-invalid'] === true));

  // 清空全部时段提交预检，后端返回 422 input.fields.periods。
  while (findButton(tree, '移除第 1 段')) {
    findButton(tree, '移除第 1 段').props.onClick({ currentTarget: {} });
    tree = renderRange();
  }
  previewError = serverPeriodsRejection('input.fields.periods');
  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderRange();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), restToWorkMessage);
  assert.equal(countVisible(tree, restToWorkMessage), 1, 'CalendarRangeDialog 预检 422 空时段报错完整可见且只出现 1 次');

  // command.error 携带 fields.periods 时在编辑态同样由 CalendarFields 唯一呈现、Feedback 不重复输出。
  findButton(tree, '新增工作时段').props.onClick({ currentTarget: {} });
  tree = renderRange();
  findButton(tree, '移除第 1 段').props.onClick({ currentTarget: {} });
  rangeCmd = makeCommand({ phase: 'rejected', error: serverPeriodsRejection('fields.periods') });
  tree = renderRange();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(countVisible(tree, restToWorkMessage), 1, 'CalendarRangeDialog command.error 不重复渲染');

  // 3. OperatorCalendarPanel：零工时提醒、客户端时段错误、服务端 422 空时段报错及休息态防吞错。
  resetHooks();
  queryResult = {
    result: {
      data: { year: 2026, month: 10, operator_ref: ref, days: [blank], cells: [blank, null, null, null, null, null, null],
        stats: { configured: 0, work_days: 0 }, write_context: opWriteContext, previous_month: null, next_month: null },
      warnings: []
    },
    loading: false,
    error: null,
    reload() {}
  };
  let opCmd = makeCommand();
  const renderPanel = () => render(w.OperatorCalendarPanel, {
    adapter: { query() {}, preview() {} },
    entity: { ref, business_code: 'OP-1' },
    source: 'production',
    command: opCmd,
    onClose() {},
    refreshState: {},
    onRefresh() {},
    Feedback: w.ResourceForms.Feedback
  });
  tree = renderPanel();
  await nodes(tree).find(node => node.props && node.props['data-operator-calendar-date'] === date).props.onClick();
  tree = renderPanel();
  assert.equal(timeInputs(tree).length, 4, '没单独设置的一天默认带两段工作时段');
  assert.equal(notes(tree).length, 0, '有工作时段不提醒');

  // 制造重叠时段并点击「保存这一天」：客户端时段错误带 role="alert" 且只出现 1 次。
  times = timeInputs(tree);
  times[2].props.onChange({ target: { value: '11:00' } });
  tree = renderPanel();
  findButton(tree, '保存这一天').props.onClick({ currentTarget: {} });
  tree = renderPanel();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), overlapMessage);
  assert.equal(countVisible(tree, overlapMessage), 1, 'OperatorCalendarPanel 客户端时段错误只出现 1 次');
  assert(timeInputs(tree).every(input => input.props['aria-invalid'] === true));

  // 移除全部时段：零工时提醒显示且不拦保存；后端返回 422 fields.periods 时错误正文完整可见。
  while (findButton(tree, '移除第 1 段')) {
    findButton(tree, '移除第 1 段').props.onClick({ currentTarget: {} });
    tree = renderPanel();
  }
  assert.equal(notes(tree).length, 1, '上班但工作时段全部移除时提醒');
  assert.equal(findButton(tree, '保存这一天').props.disabled, false, '提醒不拦保存');
  opCmd = makeCommand({ phase: 'rejected', error: serverPeriodsRejection('input.fields.periods') });
  tree = renderPanel();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), restToWorkMessage);
  assert.equal(countVisible(tree, restToWorkMessage), 1, 'OperatorCalendarPanel 后端 422 空时段报错完整可见且只出现 1 次');

  // 切换到「休息」：效率取消必填并禁用；此时 WorkPeriodFields 已卸载，activePaths 不再排除 fields.periods，避免静默吞错。
  const effInput = () => nodes(tree).find(node => node.type === 'input' && node.props.type === 'number');
  assert.equal(effInput().props['aria-required'], true);
  assert.equal(effInput().props.disabled, false);
  findButton(tree, '休息').props.onClick();
  opCmd = makeCommand();
  tree = renderPanel();
  assert.equal(notes(tree).length, 0, '休息不提醒');
  assert.equal(effInput().props['aria-required'], undefined, '个人日历切到休息时效率取消必填');
  assert.equal(effInput().props.disabled, true, '个人日历切到休息时禁用效率输入框');
  opCmd = makeCommand({ phase: 'rejected', error: serverPeriodsRejection('fields.periods') });
  tree = renderPanel();
  assert.equal(fieldAlerts(tree).length, 0, '休息态卸载了 WorkPeriodFields');
  assert.equal(countVisible(tree, restToWorkMessage), 1, '休息态下未挂载的 fields.periods 由底部 Feedback 兜底展示，绝不吞错');

  // 4. CalendarDefaultsDialog：本地空时段/重叠报错与后端 422 periods 报错唯一呈现，读取错误独立保留。
  resetHooks();
  const defaultsPayload = {
    data: { periods: factoryDefault, hours: 8, write_context: calendarWriteContext },
    meta: { source: 'production' }
  };
  queryResult = { result: defaultsPayload, loading: false, error: null, reload() {} };
  let defaultsCmd = makeCommand();
  const renderDefaults = () => render(w.CalendarDefaultsDialog, {
    adapter: { query: async () => defaultsPayload },
    command: defaultsCmd,
    onClose() {},
    refreshState: {},
    onRefresh() {}
  });
  tree = renderDefaults();
  // 模拟 useEffect 将读取到的默认时段初始化进表单草稿：此处通过真实 hooks 重跑前注入或直接读取：
  // CalendarDefaultsDialog 在 useEffect 中由 request.result 初始化 base 与 periods，我们启用一次轻量 effect 同步。
  {
    const prevEffect = context.React.useEffect;
    context.React.useEffect = fn => { fn(); };
    try { tree = renderDefaults(); tree = renderDefaults(); }
    finally { context.React.useEffect = prevEffect; }
  }
  assert.equal(timeInputs(tree).length, 2, '默认工作时间弹窗加载初始时段');

  // 删空全部时段点保存：本地校验报「至少填写一个工作时段。」，只出现 1 次且带 role="alert"。
  findButton(tree, '移除第 1 段').props.onClick({ currentTarget: {} });
  tree = renderDefaults();
  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderDefaults();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), emptyDefaultMessage);
  assert.equal(countVisible(tree, emptyDefaultMessage), 1, 'CalendarDefaultsDialog 空时段报错只出现 1 次');

  // 新增两段重叠时段点保存：客户端重叠报错只出现 1 次且带 role="alert"。
  findButton(tree, '新增工作时段').props.onClick({ currentTarget: {} });
  tree = renderDefaults();
  findButton(tree, '新增工作时段').props.onClick({ currentTarget: {} });
  tree = renderDefaults();
  times = timeInputs(tree);
  times[0].props.onChange({ target: { value: '08:00' } });
  tree = renderDefaults(); times = timeInputs(tree);
  times[1].props.onChange({ target: { value: '12:00' } });
  tree = renderDefaults(); times = timeInputs(tree);
  times[2].props.onChange({ target: { value: '11:00' } });
  tree = renderDefaults(); times = timeInputs(tree);
  times[3].props.onChange({ target: { value: '15:00' } });
  tree = renderDefaults();
  await nodes(tree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  tree = renderDefaults();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), overlapMessage);
  assert.equal(countVisible(tree, overlapMessage), 1, 'CalendarDefaultsDialog 客户端重叠报错只出现 1 次');
  assert(timeInputs(tree).every(input => input.props['aria-invalid'] === true));

  // 改为合法时段后，模拟后端返回 422 periods 错误：由 WorkPeriodFields 内联呈现且不重复。
  times = timeInputs(tree);
  times[2].props.onChange({ target: { value: '13:00' } });
  const serverDefaultMsg = '默认工作时间至少需要一个工作时段。';
  defaultsCmd = makeCommand({ phase: 'rejected', error: serverPeriodsRejection('periods', serverDefaultMsg) });
  tree = renderDefaults();
  assert.equal(fieldAlerts(tree).length, 1);
  assert.equal(visible(fieldAlerts(tree)[0]), serverDefaultMsg);
  assert.equal(countVisible(tree, serverDefaultMsg), 1, 'CalendarDefaultsDialog 后端 422 periods 报错只出现 1 次');

  // 同时存在读取错误 request.error 时，读取错误不被 periods excludePaths 吞掉。
  const readFailMsg = '默认工作时间读取不完整，请刷新后重试。';
  queryResult = { result: defaultsPayload, loading: false, error: w.APSResourceContract.failure(readFailMsg), reload() {} };
  tree = renderDefaults();
  assert.equal(countVisible(tree, readFailMsg), 1, 'CalendarDefaultsDialog 读取错误独立完整显示');
  assert.equal(countVisible(tree, serverDefaultMsg), 1);

  // 5. 校验已构建的正式静态包 static/workbench/app/main.js 同样具备相同的单点归属契约。
  const { spawnSync } = require('node:child_process');
  const bundleCheck = spawnSync(process.execPath, [path.join(__dirname, '_support/gantt_current_runtime.cjs')], {
    cwd: root,
    encoding: 'utf8',
    timeout: 15000,
    input: JSON.stringify({
      root,
      program: `
        const APSWorkbenchTransport = h.module('shared/network/transport.js');
        const CalendarDayDialog = h.module('CalendarDayDialog.jsx').CalendarDayDialog;
        const WorkPeriodFields = h.module('WorkPeriodFields.jsx').WorkPeriodFields;
        const APSResourceContract = h.module('resource-contract.js');
        const msg = ${JSON.stringify(restToWorkMessage)};
        const rejectedErr = APSWorkbenchTransport.failure({
          ok: false, committed: false,
          error: { code: 'invalid_input', message: msg, fields: [{ path: 'input.fields.periods', message: msg }], retryable: false, request_ref: '1'.repeat(32) }
        }, 422);
        const cmd = { phase: 'rejected', locked: false, stale: false, error: rejectedErr, result: null, reset: () => true, clearRejection: () => false, submit() {} };
        const dayDto = {
          date: '2026-10-01', day: 1, weekday: 3, is_weekend: false, is_today: false,
          explicit: true, calendar_ref: 'b'.repeat(48), entity: { ref: 'b'.repeat(48) }, stored: { day_type: 'holiday', efficiency: 1, allow_normal: 'no', allow_urgent: 'no' },
          default_periods: [{ start: '08:00', end: '16:00', day_offset: 0 }],
          write_context: { write_token: 'tok', capabilities: { 'calendar.upsert': true, 'calendar.delete': true }, blocked_reasons: [] },
          fields: { type: 'work', hours: 0, eff: 100, allowNormal: 'yes', allowUrgent: 'yes', note: null, periods: [] },
          effective: { is_working: false, window_start: '2026-10-01T00:00:00', window_end: '2026-10-01T00:00:00', periods: [] }
        };
        const tree = h.render(CalendarDayDialog, { adapter: {}, day: dayDto, source: 'production', command: cmd, onClose() {}, refreshState: {}, onRefresh() {} });
        const alerts = h.walk(tree).filter(n => n.props && n.props.role === 'alert' && /\\bwb-field-error\\b/.test(n.props.className || ''));
        assert.strictEqual(alerts.length, 1);
        assert.strictEqual(h.text(alerts[0]), msg);

        let periods = [
          { start: '22:00', end: '00:00', day_offset: 0 },
          { start: '01:00', end: '03:00', day_offset: 1 }
        ];
        const selectsOf = root => h.walk(root).filter(n => n.type === 'select');
        let pfTree = h.render(WorkPeriodFields, { value: periods, path: 'fields.periods', disabled: false, onChange: next => { periods = next; } });
        assert.strictEqual(selectsOf(pfTree)[0].props.disabled, true);
        assert.strictEqual(selectsOf(pfTree)[1].props.disabled, false);
        h.walk(pfTree).find(n => n.type === 'button' && h.text(n).includes('移除第 1 段')).props.onClick({ currentTarget: {} });
        assert.strictEqual(periods.length, 1);
        assert.strictEqual(periods[0].day_offset, 1);
        const offsetMsg = ${JSON.stringify(firstDayOffsetMessage)};
        const offsetErr = APSResourceContract.failure(offsetMsg, [{ path: 'fields.periods', message: offsetMsg }]);
        pfTree = h.render(WorkPeriodFields, { value: periods, path: 'fields.periods', disabled: false, onChange: next => { periods = next; } });
        assert(h.text(pfTree).includes(offsetMsg));
        assert.strictEqual(selectsOf(pfTree)[0].props.disabled, false);
        const invalidPfTree = h.render(WorkPeriodFields, { value: periods, path: 'fields.periods', error: offsetErr, disabled: false, onChange: next => { periods = next; } });
        assert.strictEqual(selectsOf(invalidPfTree)[0].props['aria-invalid'], true);
        selectsOf(pfTree)[0].props.onChange({ target: { value: '0' } });
        assert.strictEqual(periods[0].day_offset, 0);
        pfTree = h.render(WorkPeriodFields, { value: periods, path: 'fields.periods', disabled: false, onChange: next => { periods = next; } });
        assert(!h.text(pfTree).includes(offsetMsg));
        assert(h.text(pfTree).includes('实际工作 2 小时；时段之间不排产。'));
        assert.strictEqual(selectsOf(pfTree)[0].props.disabled, true);
      `
    })
  });
  assert.equal(bundleCheck.status, 0, bundleCheck.stdout + bundleCheck.stderr);

  console.log('calendar zero-hour workday notes and single-owner period alerts verified across all 4 calendar surfaces');
})().catch(error => { console.error(error); process.exit(1); });
