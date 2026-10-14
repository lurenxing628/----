'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const names = ['resource-contract.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'PlanGanttModel.js', 'ResourceControls.jsx', 'RunHistoryAPI.js', 'RunDecisionComparison.jsx', 'DecisionHistoryAPI.js', 'DeliveryProjectionContract.js', 'TrialContract.js', 'DecisionHistoryChart.jsx', 'DecisionHistoryDetails.jsx', 'DecisionHistoryWorkspace.jsx', 'RunHistoryWorkspace.jsx', 'SchedulingWorkspace.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: names.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })), check_combined: true }).outputs;
const clone = value => JSON.parse(JSON.stringify(value)), ref = n => n.toString(16).padStart(48, '0'), token = 'h'.repeat(32);
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(value => value !== null && value !== undefined && value !== false) });
const nodes = tree => !tree || typeof tree !== 'object' ? [] : [tree, ...tree.children.flatMap(nodes)];
const text = tree => tree == null ? '' : typeof tree !== 'object' ? String(tree) : tree.children.map(text).join(' ');
function expand(tree) { if (!tree || typeof tree !== 'object') return tree; if (typeof tree.type === 'function') return expand(tree.type({ ...tree.props, children: tree.children })); return { ...tree, children: tree.children.map(expand) }; }
function hooks() {
  let cursor = 0; const slots = [], effects = [], same = (a, b) => a && b && a.length === b.length && a.every((value, i) => value === b[i]);
  const useEffect = (effect, deps) => { const i = cursor++, old = slots[i]; if (!old || !same(old.deps, deps)) { slots[i] = { deps }; effects.push(effect); } };
  return { React: { createElement: h, Fragment: 'fragment', useId: () => 'history-chart', createContext: () => ({ Provider: 'provider' }), Children: { map: (value, apply) => value == null ? value : [value].flat().map(apply) }, cloneElement: (value, props) => ({ ...value, props: { ...value.props, ...props } }), useEffect, useLayoutEffect: useEffect,
    useRef(initial) { const i = cursor++; if (!slots[i]) slots[i] = { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, value => { slots[i].value = typeof value === 'function' ? value(slots[i].value) : value; }]; },
    useMemo(make, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: make() }; return slots[i].value; },
    useReducer(reducer, initial) { const [value, setValue] = this.useState(initial); return [value, action => setValue(old => reducer(old, action))]; } },
    render(make) { cursor = 0; return make(); }, flush() { while (effects.length) effects.shift()(); } };
}
function runtime(state = hooks()) {
  const snapshots = [], document = { hidden: false, activeElement: null }, window = { document, ResourceControls: { Button: 'button', Modal: 'modal', Icon: 'icon' }, RunHistoryControls: { Button: 'button', ErrorBox: 'error', Filters: 'catalog-filters', Table: 'catalog-table', Pager: 'catalog-pager' },
    WorkbenchListControls: { Pager: 'pager', EmptyState: 'empty-state' }, WorkbenchReference: 'reference', WorkbenchPageContext: { useSnapshot: value => snapshots.push(clone(value)) },
    RunJobAPI: { create: () => ({}) }, RunJobControls: { Button: 'button' }, RunCandidateWorkspace: 'candidate-workspace', PlanWorkspace: 'plan-workspace',
    WorkbenchDatePickerModel: { factoryTime: value => value.replace(' ', 'T') }, fetch: () => { throw new Error('Unexpected live fetch'); } };
  for (const output of built) vm.runInNewContext(output.code, { React: state.React, window, AbortController, DOMException, URLSearchParams, setTimeout, clearTimeout, document });
  const sharedButton = window.ResourceControls.Button;
  Object.assign(window.ResourceControls, { Button: 'button', Modal: 'modal', Icon: 'icon' }); window.WorkbenchListControls.EmptyState = window.ResourceControls.EmptyState;
  return { window, state, snapshots, sharedButton };
}
const { window } = runtime(), A = window.DecisionHistoryAPI;
const keys = ['overdue_count', 'machine_utilization_ratio'];
const definitions = [{ key: keys[0], label: '超期批次', group: 'delivery', unit: '批次', precision: 0, improvement: 'lower', scope: 'full_admission', source: 'archived_delivery', common: true, metric_version: 'decision-delivery-v1' },
  { key: keys[1], label: '设备占用比例', group: 'resources', unit: '%', precision: 1, improvement: 'neutral', scope: 'fixed_resource_window', source: 'archived_resource_calendar', common: false, metric_version: 'decision-resource-v4' }];
function metric(value, unit, extra = {}) { return { value, state: value === null ? 'unavailable' : 'complete', known_subtotal: value, known_count: value === null ? 0 : 1, unknown_count: value === null ? 1 : 0, total_count: 1,
  scope: unit === '%' ? 'fixed_resource_window' : 'full_admission', metric_version: unit === '%' ? 'decision-resource-v4' : 'decision-delivery-v1', reason: value === null ? { code: 'not_recorded', message: '原来源未保存。' } : null,
  source: { kind: 'run_archive', ref: ref(1), path: 'saved.metrics' }, unit, covered_batch_refs: [ref(101)], covered_operation_refs: [ref(201)], covered_resource_refs: unit === '%' ? [ref(301)] : null,
  numerator_hours: unit === '%' && value !== null ? 1 : null, denominator_hours: unit === '%' && value !== null ? 8 : null, unknown_workload_count: 0, ...extra }; }
const windowScope = { mode: 'fixed_days', start: '2026-10-01T08:30:12.250123', end: '2026-10-08T08:30:12.250123', days: 7, anchor: 'source_start', time_basis: 'factory_local', boundary: 'half_open', state: 'available', reason: null,
  cohort: { machine_refs: [ref(301)], operator_refs: [ref(401)] } };
function entry(n, value, ratio, occurred = '2026-10-0' + n + 'T10:00:00') {
  return { entry_ref: 'run:' + ref(n), timeline: 'run', source_kind: 'run', label: '保存运行 ' + n, occurred_at: occurred, time_basis: 'accepted_at_factory_local', state: n === 3 ? 'failed' : 'complete',
    identity: { run_ref: ref(n), candidate_ref: ref(n + 10), scenario_ref: null, draft_ref: null, plan_ref: null, plan_version: null, history_id: null, receipt_ref: null, request_key: null },
    times: { accepted_at: occurred, started_at: occurred, finished_at: occurred, adopted_at: null, committed_at_utc: null, schedule_time: null }, baseline: { plan_ref: null, version: 0 },
    source: { kind: 'run', ref: ref(n), state: n === 3 ? 'unavailable' : 'available', reason: n === 3 ? { code: 'failed', message: '保存的计算失败。' } : null },
    scope: { state: 'complete', batch_refs: [ref(101)], operation_refs: [ref(201)], batch_count: 1, operation_count: 1, demand_hours: 8, reason: null,
      batch_quantity: metric(12, '件', { source: { kind: 'run_archive', ref: ref(n), path: 'Batches.quantity' } }) },
    reading_context: { resource_window: clone(windowScope), metric_basis: 'common_projection' }, metrics: { [keys[0]]: metric(value, '批次'), [keys[1]]: metric(ratio, '%') },
    navigation: [{ label: '查看保存候选', view: 'analysis', context: { run_ref: ref(n), candidate_ref: ref(n + 10) }, enabled: true, reason: null }], issues: [] };
}
function conditionGroup(rows = [], size = 20) { return { state: rows.length ? 'different' : 'unknown', summary: { equal: 0, different: rows.length, unknown: 0 }, categories: rows.length ? [{ key: 'batches', label: '批次', state: 'different', summary: { equal: 0, different: rows.length, unknown: 0 } }] : [], rows, page: { number: 1, size, total: rows.length, has_more: false } }; }
function payload(input = {}) {
  const q = A.scope({ metric_keys: keys, order: 'asc', ...input }), all = [entry(1, 0, 0), entry(2, 3, 0.125), entry(3, null, null), entry(4, 2, 0.5), entry(5, 0, null, null)];
  const entries = all.slice((q.page - 1) * q.size, q.page * q.size), selected = all.find(row => row.entry_ref === q.selected_entry_ref) || null, reference = all.find(row => row.identity.run_ref === q.reference_run_ref) || null;
  if (q.range_start) all.forEach(row => Object.assign(row.reading_context.resource_window, { mode: 'absolute', start: q.range_start, end: q.range_end, days: null, anchor: 'common_absolute_window' }));
  const filters = clone(q); delete filters.snapshot_ref;
  return { ok: true, schema_version: 1, meta: { request_ref: 'r'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: q.snapshot_ref || token, as_of: '2026-10-14T12:00:00' }, warnings: [], data: {
    history_version: 'decision-history-v1', filters, entries, page: { number: q.page, size: q.size, total: all.length, has_more: q.page * q.size < all.length }, totals: { run: all.length, official: 0, filtered: all.length }, metric_definitions: clone(definitions),
    selection: { entry: selected, reference }, comparison: { mode: q.comparison, conditions: conditionGroup([], q.condition_size), configurations: conditionGroup([], 0), objective: null, metric_deltas: {},
      conclusion: { state: q.comparison === 'observed' ? 'observed' : 'unavailable', message: '保存来源的实际观测。', reason: null, improved_metric_keys: [], worsened_metric_keys: [] } },
    trend: { point_scope: 'current_page', order: 'asc', points: entries.map((row, index) => ({ entry_ref: row.entry_ref, occurred_at: row.occurred_at, time_basis: row.time_basis, label: row.label, state: row.state,
      metrics: row.metrics, scope: row.scope, resource_window: row.reading_context.resource_window, range_changed: index === 3, condition_state: 'not_compared', connections: Object.fromEntries(keys.map(key => [key, index === 1])) })) },
    resource_window: Object.fromEntries(Object.entries(all[0].reading_context.resource_window).filter(([key]) => !['state', 'reason', 'cohort'].includes(key))) } };
}
function queryAndResponse() {
  const value = payload(), q = value.data.filters; assert.strictEqual(A.history(value, q), value.data);
  assert.deepEqual(clone(A.scope({})).metric_keys, ['overdue_count', 'total_tardiness_hours', 'makespan_hours', 'elapsed_seconds']);
  const absolute = A.scope({ range_start: windowScope.start, range_end: windowScope.end }); assert.equal(absolute.range_start, windowScope.start, '共同窗口保留工厂本地微秒');
  for (const wrong of [{ extra: 'ignored' }, { size: 10 }, { condition_size: 7 }, { metric_keys: ['a', 'a'] }, { date_from: '2026-10-01' }, { range_start: windowScope.start }, { selected_entry_ref: ref(1) }]) assert.throws(() => A.scope(wrong));
  const params = A.serialized(A.scope({ metric_keys: keys })); assert.equal(params.get('metric_keys'), keys.join(',')); assert.equal(params.has('snapshot_ref'), false);
  const reject = mutate => { const changed = clone(value); mutate(changed); assert.throws(() => A.history(changed, q)); };
  reject(changed => { changed.data.trend.points[0].metrics[keys[0]].value = 9; });
  reject(changed => { changed.data.trend.points[1].metrics[keys[0]].metric_version = 'saved-other'; changed.data.entries[1].metrics[keys[0]].metric_version = 'saved-other'; });
  reject(changed => { changed.data.selection.entry = changed.data.entries[0]; });
  reject(changed => { changed.meta.snapshot_ref = 'new-snapshot'; changed.data.filters.page = 2; });
  const bound = A.scope({ ...q, snapshot_ref: token }); assert.throws(() => A.history({ ...value, meta: { ...value.meta, snapshot_ref: 'new-snapshot' } }, bound), error => error.code === 'snapshot_stale');
  const official = clone(value.data.entries[0]); official.timeline = 'official'; official.source_kind = 'candidate_adoption'; official.identity.receipt_ref = 'a'.repeat(32); official.entry_ref = 'adoption:' + official.identity.receipt_ref; A.entry(official, keys); official.source_kind = 'trial_adoption'; A.entry(official, keys);
  official.source_kind = 'legacy_official'; official.identity.history_id = 7; official.entry_ref = 'legacy:7'; A.entry(official, keys);
  assert.equal(A.metricText(metric(0, '小时'), { precision: 2 }), '0 小时'); assert.equal(A.metricText(metric(null, '小时'), { precision: 2 }), '未知'); assert.equal(A.metricText(metric(0.125, '%'), { precision: 1 }), '12.5%');
}
function chartAndDetails() {
  const value = payload(), before = JSON.stringify(value), selected = [], reveals = [], chart = window.DecisionHistoryChart.Chart({ data: value.data, metricKey: keys[1], selectedEntryRef: value.data.entries[0].entry_ref, onSelect: (row, reveal) => { selected.push(row); reveals.push(reveal); } });
  const records = nodes(chart).filter(node => node.type === 'button' && node.props['data-metric-value'] !== undefined), group = nodes(chart).find(node => node.props.className === 'dh-chart-keyboard');
  assert.deepEqual(records.map(node => node.props['data-metric-value']), [0, 0.125, 0.5]); assert(text(records[1]).includes('12.5%'), '百分比保留原倍率'); assert.equal(nodes(nodes(chart).find(node => node.props.className === 'dh-chart-y-axis')).find(node => node.type === 'span' && text(node) === '25%').props.title, '25%', '轴提示与可见百分数保持同单位');
  assert.deepEqual(nodes(chart).filter(node => node.type === 'line').map(node => node.props['data-gap-count']), [0, 1], '相邻实线、真实缺项虚线');
  assert(text(chart).replace(/\s+/g, ' ').includes('1 条待确认／不适用')); assert.equal(nodes(chart).filter(node => node.props.className === 'dh-chart-missing-entry').length, 2);
  assert.equal(nodes(chart).filter(node => node.type === 'svg').length, 1); assert(!nodes(chart).some(node => ['circle', 'path'].includes(node.type)), 'SVG只承载线段');
  assert(!nodes(chart).find(node => node.props['aria-live'] === 'polite').props.className.includes('visually-hidden'), '当前记录说明可见');
  const event = (key, target) => ({ key, target, currentTarget: group, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } });
  for (const key of ['ArrowRight', 'ArrowDown']) { group.props.onKeyDown(event(key)); assert.strictEqual(selected.at(-1), value.data.entries[1]); } for (const key of ['ArrowLeft', 'ArrowUp']) { group.props.onKeyDown(event(key)); assert.strictEqual(selected.at(-1), value.data.entries[0]); }
  group.props.onKeyDown(event('End')); assert.strictEqual(selected.at(-1), value.data.entries[4]); group.props.onKeyDown(event('Home')); assert.strictEqual(selected.at(-1), value.data.entries[0]); assert.equal(reveals.at(-1), false, '完整points键盘选择包含缺项并保持图位置');
  group.props.onKeyDown(event('Enter')); assert.strictEqual(selected.at(-1), value.data.entries[0]); assert.equal(reveals.at(-1), true);
  const focusedButton = { closest: () => focusedButton, getAttribute: () => records[1].props['data-dh-chart-choice'] }, enter = event('Enter', focusedButton), count = selected.length;
  group.props.onKeyDown(enter); group.props.onKeyDown(enter); assert.equal(selected.length, count + 1); assert.strictEqual(selected.at(-1), value.data.entries[1]); assert.equal(enter.defaultPrevented, true, '原生Enter选择聚焦按钮自身一次并取消native重复click');
  const space = event(' ', focusedButton); group.props.onKeyDown(space); assert.equal(space.defaultPrevented, false); records[1].props.onClick(); assert.equal(selected.length, count + 2); assert.equal(reveals.at(-1), true, 'Space和鼠标沿原生click');
  const summaryEvent = event('Enter', { closest: () => null }); group.props.onKeyDown(summaryEvent); assert.equal(summaryEvent.defaultPrevented, false, '缺项summary保留原生开合');
  const busyChart = window.DecisionHistoryChart.Chart({ data: value.data, metricKey: keys[1], selectedEntryRef: null, busy: true, onSelect: () => assert.fail('Busy chart selected') }); nodes(busyChart).find(node => node.props.className === 'dh-chart-keyboard').props.onKeyDown(event('End'));
  const countChart = window.DecisionHistoryChart.Chart({ data: value.data, metricKey: keys[0], selectedEntryRef: value.data.entries[4].entry_ref });
  const untimed = nodes(countChart).find(node => node.props.className === 'dh-chart-untimed'); assert(text(untimed).includes('0 批次'), '缺时间真实值独立保留'); assert.equal(nodes(untimed).filter(node => node.type === 'button').length, 1);
  const lineValue = payload(), actualValues = new Map([[1, 2], [2, 2], [3, 2], [7, 0], [15, 12]]);
  lineValue.data.entries = Array.from({ length: 15 }, (_, index) => { const n = index + 1, row = entry(n, actualValues.has(n) ? actualValues.get(n) : null, 0, n === 2 || n === 3 ? '2026-10-13T02:03:44' : '2026-10-14T02:38:50.246069'); row.label = '保存的第' + n + '次运行'; row.scope.batch_count = n <= 3 ? 6 : n === 7 ? 11 : 12; return row; });
  lineValue.data.trend.points = lineValue.data.entries.map(row => ({ ...value.data.trend.points[0], entry_ref: row.entry_ref, label: row.label, occurred_at: row.occurred_at, metrics: row.metrics, scope: row.scope, connections: { [keys[0]]: false, [keys[1]]: false } }));
  Object.assign(lineValue.data.entries[5].metrics[keys[0]], { state: 'partial', known_count: 18, known_subtotal: 3, unknown_count: 2, covered_operation_refs: null }); lineValue.data.entries[5].scope.batch_count = 21;
  const lineChart = window.DecisionHistoryChart.Chart({ data: lineValue.data, metricKey: keys[0], selectedEntryRef: lineValue.data.entries[2].entry_ref, onSelect: row => selected.push(row) });
  const lineRecords = nodes(lineChart).filter(node => node.props.className === 'dh-chart-entry'), lines = nodes(lineChart).filter(node => node.type === 'line');
  assert.deepEqual(lineRecords.map(node => node.props['data-metric-value']), [2, 2, 2, 0, 12]); assert.deepEqual(lines.map(node => node.props['data-gap-count']), [0, 0, 3, 7]);
  assert.equal(lines[0].props.x2, lines[1].props.x1); assert.equal(lines[0].props.y2, lines[1].props.y1); assert.equal(lines[0].props.x2 - lines[0].props.x1, lines[1].props.x2 - lines[1].props.x1, '同时间两条分别占等距位置');
  lineRecords[1].props.onClick(); assert.strictEqual(selected.at(-1), lineValue.data.entries[1]); lineRecords[2].props.onClick(); assert.strictEqual(selected.at(-1), lineValue.data.entries[2]);
  assert(text(lineRecords[1]).includes('保存的第2次运行') && text(lineRecords[1]).includes('共 6 批')); assert(text(lineChart).replace(/\s+/g, ' ').includes('3 条待确认／不适用') && text(lineChart).replace(/\s+/g, ' ').includes('7 条待确认／不适用'));
  assert(text(nodes(lineChart).find(node => node.props.className === 'dh-chart-missing-entry' && node.props['data-entry-ref'] === 'run:' + ref(6))).includes('已知 3 批次，另有 2 批待确认'));
  const partialChart = window.DecisionHistoryChart.Chart({ data: lineValue.data, metricKey: keys[0], selectedEntryRef: lineValue.data.entries[5].entry_ref }); assert(text(nodes(partialChart).find(node => node.props['aria-live'] === 'polite')).includes('已知 3 批次，另有 2 批待确认'), '缺项行与当前摘要沿同一实际粒度');
  const compared = clone(lineValue); compared.data.comparison.mode = 'same_conditions'; compared.data.selection.reference = compared.data.entries[2]; compared.data.trend.points.forEach(point => { point.connections[keys[0]] = true; point.range_changed = true; });
  const comparedChart = window.DecisionHistoryChart.Chart({ data: compared.data, metricKey: keys[0], selectedEntryRef: compared.data.entries[1].entry_ref });
  assert.deepEqual(nodes(comparedChart).filter(node => node.type === 'line').map(node => clone(node.props)), lines.map(node => clone(node.props)), '对照不改变原值连线');
  assert.deepEqual(nodes(comparedChart).filter(node => node.props.className === 'dh-chart-point-space').map(node => clone(node.props.style)), nodes(lineChart).filter(node => node.props.className === 'dh-chart-point-space').map(node => clone(node.props.style)), '对照不改变原值点位置');
  const changedBasis = clone(lineValue); changedBasis.data.trend.points[1].metrics[keys[0]].metric_version = 'other-version'; changedBasis.data.trend.points[4].metrics[keys[0]].unit = '小时'; changedBasis.data.trend.points[8].metrics[keys[0]].scope = 'other-scope';
  const changedChart = window.DecisionHistoryChart.Chart({ data: changedBasis.data, metricKey: keys[0], selectedEntryRef: null }); assert.equal(nodes(changedChart).filter(node => node.type === 'line').length, 0, '端点版本变化、中途单位和scope变化均断线');
  const zeroPair = payload(); for (const index of [0, 1]) Object.assign(zeroPair.data.entries[index].metrics[keys[1]], { value: 0, known_subtotal: 0, state: 'not_applicable' });
  assert.strictEqual(A.history(zeroPair, zeroPair.data.filters), zeroPair.data, '数值0的not_applicable仍沿原service合同读取');
  let zeroChart = window.DecisionHistoryChart.Chart({ data: zeroPair.data, metricKey: keys[1], selectedEntryRef: zeroPair.data.entries[0].entry_ref }); assert.equal(nodes(zeroChart).filter(node => node.type === 'button' && node.props['data-metric-value'] === 0).length, 2);
  zeroPair.data.trend.points.forEach(point => Object.assign(point.metrics[keys[1]], { value: 0, known_subtotal: 0, state: 'complete' })); zeroChart = window.DecisionHistoryChart.Chart({ data: zeroPair.data, metricKey: keys[1], selectedEntryRef: null });
  assert.equal(nodes(zeroChart).filter(node => node.type === 'button' && node.props['data-metric-value'] === 0).length, 4); assert.equal(nodes(zeroChart).filter(node => node.type === 'line').length, 3); assert(nodes(zeroChart).filter(node => node.type === 'line').every(node => node.props.y1 === 210 && node.props.y2 === 210), '全0保持0点和水平线');
  const smallCounts = clone(value); smallCounts.data.trend.points[1].metrics[keys[0]].value = 1;
  const smallChart = window.DecisionHistoryChart.Chart({ data: smallCounts.data, metricKey: keys[0], selectedEntryRef: null }), tickLabels = nodes(nodes(smallChart).find(node => node.props.className === 'dh-chart-y-axis')).filter(node => node.type === 'span').map(text);
  assert.deepEqual(tickLabels, ['0', '1', '2'], '小计数刻度是互异整数');
  const unavailable = clone(value); unavailable.data.trend.points.forEach(point => Object.assign(point.metrics[keys[0]], { value: null, state: 'unavailable', known_count: 0, known_subtotal: 0 }));
  Object.assign(unavailable.data.trend.points[1].metrics[keys[0]], { state: 'partial', known_count: 1, known_subtotal: 0, unknown_count: 1 });
  let missingChart = window.DecisionHistoryChart.Chart({ data: unavailable.data, metricKey: keys[0], selectedEntryRef: unavailable.data.entries[0].entry_ref });
  assert(text(missingChart).includes('本页没有可绘制的数值')); assert.equal(nodes(missingChart).filter(node => node.props.className === 'dh-chart-entry').length, 0);
  const missingRows = nodes(missingChart).filter(node => node.props.className === 'dh-chart-missing-entry'); assert(!text(missingRows[0]).includes('已知')); assert(text(missingRows[1]).includes('已知 0 批次'), 'known_count为0不报0小计，有真实已知0则保留');
  assert(!nodes(missingChart).find(node => node.props['aria-live'] === 'polite').props.className.includes('visually-hidden')); assert(text(nodes(missingChart).find(node => node.props['aria-live'] === 'polite')).includes('待确认'));
  assert.equal(JSON.stringify(value), before, '绘图与百分比格式不改业务DTO');
  const selectedData = payload({ selected_entry_ref: 'run:' + ref(2) }).data, opened = [], changes = [];
  let detail = expand(h(window.DecisionHistoryDetails.Details, { data: selectedData, query: selectedData.filters, onOpen: target => opened.push(target), onQuery: (...args) => changes.push(args), canNavigate: true }));
  const source = expand(h(window.DecisionHistoryDetails.Sources, { data: selectedData, result: payload() })); assert(text(source).includes('当时无正式计划')); assert(!text(source).includes('第 0 版')); assert(text(detail).replace(/\s+/g, ' ').includes('批次原数量合计 12 件'));
  assert(!nodes(detail).some(node => node.props['aria-label'] === '八类生产条件判断'), '无基准业务走势不铺未知对照');
  assert.equal(nodes(detail).filter(node => node.type === 'p' && text(node).startsWith('已知小计')).length, 0, '完整已知值默认只呈现一次');
  nodes(detail).find(node => node.type === 'button' && text(node) === '查看保存候选').props.onClick(); assert.strictEqual(opened[0], selectedData.selection.entry.navigation[0]);
  const capacity = clone(selectedData), availableKey = 'machine_available_hours', cvKey = 'machine_balance_cv';
  capacity.metric_definitions.push({ ...definitions[1], key: availableKey, label: '设备可排总时长', unit: '小时' }, { ...definitions[1], key: cvKey, label: '设备占用分布差异', unit: '比值' });
  capacity.selection.entry.metrics[availableKey] = metric(8, '小时'); capacity.selection.entry.metrics[cvKey] = metric(0.2, '比值', { numerator_hours: 1, denominator_hours: 8 });
  let capacityDetail = expand(h(window.DecisionHistoryDetails.Details, { data: capacity, query: capacity.filters, onQuery() {}, onOpen() {}, canNavigate: true }));
  const capacityTable = nodes(capacityDetail).find(node => node.type === 'table' && node.props['aria-label'] === '所选资源容量与分母');
  assert.equal(nodes(capacityTable).filter(node => node.type === 'tr').length, 2, '同类比值依据只呈现一份共享窗口容量'); assert(text(capacityTable).includes('窗口班内已占') && text(capacityTable).includes('窗口可排总时长'));
  capacity.metric_definitions = capacity.metric_definitions.filter(row => row.key === availableKey); capacity.selection.entry.metrics = { [availableKey]: capacity.selection.entry.metrics[availableKey] };
  capacityDetail = expand(h(window.DecisionHistoryDetails.Details, { data: capacity, query: capacity.filters, onQuery() {}, onOpen() {}, canNavigate: true }));
  assert(!nodes(capacityDetail).some(node => node.type === 'table' && node.props['aria-label'] === '所选资源容量与分母'), '已知绝对工时不冒充未知比值容量依据');
  const side = value => ({ present: true, state: 'known', value, source: { kind: 'run_archive', ref: ref(2), path: 'saved.production' }, reason: null });
  selectedData.comparison.mode = 'same_conditions'; selectedData.selection.reference = selectedData.entries[0];
  selectedData.comparison.metric_deltas[keys[1]] = { value: -0.00001, state: 'comparable', direction: 'neutral', reference_value: 0.12501, selected_value: 0.125, reason: null };
  const values = [0, false, [], null], rows = values.map((value, index) => ({ category: 'batches', entity: { key: ref(101), label: '保存批次' }, field: 'field_' + index, state: 'different', before: side(value), after: side(value) }));
  rows.push({ ...rows[0], field: 'unknown', state: 'unknown', after: { ...side(null), present: false, state: 'unknown' } }); selectedData.comparison.conditions = conditionGroup(rows);
  selectedData.selection.entry.scope.batch_quantity = metric(null, '件', { known_count: 1, unknown_count: 1, total_count: 2, known_subtotal: 12, state: 'partial' });
  detail = expand(h(window.DecisionHistoryDetails.Details, { data: selectedData, query: selectedData.filters, onOpen: target => opened.push(target), onQuery: (...args) => changes.push(args), canNavigate: true }));
  const visible = text(detail).replace(/\s+/g, ' '), savedSides = nodes(detail).filter(node => node.props['data-history-saved-state']);
  for (const preview of ['0', '否', '0 项', '空值']) assert(savedSides.some(node => node.props['data-history-saved-state'] === 'known' && node.props['data-history-value-present'] === true && text(node) === preview), '真实0/false/空集合/null保持已知原含义：' + preview);
  assert(visible.includes('未保存') && visible.includes('已知小计 12 件'));
  assert(visible.includes('减少不到 0.1 个百分点'), '微小非0百分比差值保留原倍率和百分点含义');
  const conditionDetails = nodes(detail).find(node => node.type === 'details' && text(node).startsWith('生产条件详情')); assert(conditionDetails && conditionDetails.props.open !== true, '完整条件和分页默认收起');
  const pager = nodes(conditionDetails).find(node => node.type === 'pager'); pager.props.onPage(2); pager.props.onSize(50); assert.deepEqual(clone(changes), [[{ condition_page: 2 }, true], [{ condition_page: 1, condition_size: 50 }, true]]);
  const equalData = clone(selectedData); equalData.comparison.conditions.summary = { equal: 533, different: 0, unknown: 0 }; equalData.comparison.conditions.categories = [];
  detail = expand(h(window.DecisionHistoryDetails.Details, { data: equalData, query: equalData.filters, onOpen() {}, onQuery() {}, canNavigate: true })); assert(text(detail).replace(/\s+/g, ' ').includes('生产条件相同，共 533 项'), '相同条件总数使用全量summary');

}
function navigationAndSession() {
  const start = A.context({ query: A.scope({ metric_keys: keys, selected_entry_ref: 'run:' + ref(2), reference_run_ref: ref(1), comparison: 'same_conditions', page: 2, range_start: windowScope.start, range_end: windowScope.end, snapshot_ref: token }), metric_key: keys[1] });
  const origin = { run_ref: ref(2), return_decision_history_context: start }, returned = A.historyContext(origin); assert.deepEqual(clone(returned.decision_history_context), clone(start)); assert.equal(returned.history_topic, 'decision_history');
  const trial = { scenario_ref: ref(9), return_decision_history_context: start }; assert.deepEqual(clone(window.TrialContract.target(trial)), clone(trial));
  assert.throws(() => window.TrialContract.target({ ...trial, return_decision_history_context: { query: { size: 7 } } }));
  assert.deepEqual(clone(A.historyContext({ return_decision_context: origin })), clone(returned)); assert.deepEqual(clone(A.historyContext({})), { source: 'run_history' });
  const { window: local, state, snapshots } = runtime(), links = [], requests = [], api = { history: () => {}, historyExport: () => {} }; let readLoading = false, readError = null;
  local.APSResourceSession = { useQuery: (load, deps, enabled = true) => { const query = JSON.parse(deps[1]); requests.push(query); const result = payload(query); result.data.comparison.conditions.page.number = query.condition_page; return { loading: enabled && readLoading, error: readError, result: !enabled || readLoading || readError ? null : result }; } };
  const sessionStart = A.context({ query: A.scope({ metric_keys: keys, selected_entry_ref: 'run:' + ref(2), reference_run_ref: ref(1), comparison: 'same_conditions', snapshot_ref: token }), metric_key: keys[1] });
  const props = { adapter: api, start: sessionStart, pageContext: { history_query: { page: 3 } }, onNavigate: (...args) => links.push(args) };
  let tree = state.render(() => local.DecisionHistoryViews.Session(props));
  const details = nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details); details.props.onOpen(details.props.data.selection.entry.navigation[0]);
  assert.equal(links[0][0], 'analysis'); assert.deepEqual(clone(links[0][1].return_decision_history_context.query), clone(requests.at(-1))); assert.equal(links[0][1].return_decision_history_context.metric_key, keys[1]);
  const pager = nodes(tree).find(node => node.type === 'pager'); pager.props.onPage(2); tree = state.render(() => local.DecisionHistoryViews.Session(props)); assert.equal(requests.at(-1).snapshot_ref, token); assert.equal(requests.at(-1).page, 2); assert.equal(requests.at(-1).selected_entry_ref, 'run:' + ref(2));
  nodes(tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新历史走势').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); assert.equal(requests.at(-1).snapshot_ref, null); assert.equal(requests.at(-1).page, 2); assert.equal(requests.at(-1).reference_run_ref, ref(1));
  assert.equal(snapshots.at(-1).decision_history_context.query.snapshot_ref, token);
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onEndComparison(); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  assert.equal(requests.at(-1).reference_run_ref, null); assert.equal(requests.at(-1).comparison, 'observed'); assert.equal(requests.at(-1).selected_entry_ref, 'run:' + ref(2)); assert.equal(requests.at(-1).page, 2); assert.equal(requests.at(-1).range_start, sessionStart.query.range_start);
  nodes(tree).find(node => node.type === 'pager').props.onPage(1); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onReference(payload().data.entries[0]); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  assert.equal(requests.at(-1).reference_run_ref, ref(1)); assert.equal(requests.at(-1).comparison, 'same_conditions'); assert.equal(requests.at(-1).selected_entry_ref, 'run:' + ref(2), '固定对照保留不同的已选记录');
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onReference(payload().data.entries[1]); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  assert.equal(requests.at(-1).reference_run_ref, ref(2)); assert.equal(requests.at(-1).selected_entry_ref, null, '固定自己为对照时等待另一条记录');
  const waiting = expand(h(local.DecisionHistoryDetails.Details, nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props)); assert(text(waiting).includes('请选择另一条记录'));
  let workspaceHeight = 1288.5; const focusLog = [], detailTitle = { focus: options => focusLog.push(['detail', clone(options)]), scrollIntoView: options => focusLog.push(['scroll', clone(options)]) }, graphFocus = { focus: options => focusLog.push(['chart', clone(options)]) }, rowFocus = { focus: options => focusLog.push(['row', clone(options)]) };
  nodes(tree).find(node => node.props['data-decision-history-workspace']).props.ref.current = { getBoundingClientRect: () => ({ height: workspaceHeight }), querySelectorAll: () => [], querySelector: selector => selector === '[data-history-detail-title]' ? detailTitle : selector === '.dh-chart-keyboard' ? graphFocus : selector.startsWith('[data-dh-row-choice=') ? rowFocus : null };
  state.flush(); assert.deepEqual(focusLog, [['detail', { preventScroll: true }], ['scroll', { block: 'start' }]], '用作对照聚焦摘要，并把关键内容定位到页头下方');
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onSelect(payload().data.entries[2], true); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.deepEqual(focusLog, [['detail', { preventScroll: true }], ['scroll', { block: 'start' }]], '表格点击或Enter把焦点移入结果并展示主要内容');
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[0], false); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.equal(tree.props.style.minHeight, workspaceHeight, '方向键读取保留发起前实测高度'); assert(!nodes(tree).some(node => node.type === local.DecisionHistoryChart.Chart), '保高仍隐藏旧图'); assert.deepEqual(focusLog, []);
  readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style, undefined, '读取完成解除保高');
  assert.deepEqual(focusLog, [['chart', { preventScroll: true }]], '图表方向键保留图焦点，不滚到详情');
  const horizontalLog = []; let horizontalLeft = 360;
  const chartScroll = { get scrollLeft() { return horizontalLeft; }, set scrollLeft(value) { horizontalLeft = value; horizontalLog.push(value); }, getBoundingClientRect: () => ({ left: 100, right: 500 }) };
  const chartSeries = { getAttribute: () => '%', querySelector: () => chartScroll }, rightPoint = { closest: () => chartScroll, getBoundingClientRect: () => ({ left: 860 - horizontalLeft, right: 940 - horizontalLeft }) };
  const currentWorkspace = nodes(tree).find(node => node.props['data-decision-history-workspace']).props.ref.current;
  nodes(tree).find(node => node.props['data-decision-history-workspace']).props.ref.current = { getBoundingClientRect: () => ({ height: workspaceHeight }), querySelectorAll: () => [chartSeries], querySelector: selector => selector === '.dh-chart-keyboard' ? graphFocus : selector.startsWith('.dh-chart-entry[') ? rightPoint : null };
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[1], false); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  chartScroll.scrollLeft = 0; horizontalLog.length = 0; readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.deepEqual(horizontalLog, [360, 440], '读取后先恢复原水平位置，再只移动所属容器让右侧实际按钮完整可见'); assert(rightPoint.getBoundingClientRect().left >= 100 && rightPoint.getBoundingClientRect().right <= 500); assert.deepEqual(focusLog, [['chart', { preventScroll: true }]]);
  nodes(tree).find(node => node.props['data-decision-history-workspace']).props.ref.current = currentWorkspace;
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onSelect(payload().data.entries[3], false); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.deepEqual(focusLog, [['row', { preventScroll: true }]], '记录行方向键保留行焦点，不滚到详情');
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onEndComparison(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.deepEqual(focusLog, [['detail', { preventScroll: true }]], '结束对照保留详情焦点，不执行主动定位');
  focusLog.length = 0; nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[1], true); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.deepEqual(focusLog, [['detail', { preventScroll: true }], ['scroll', { block: 'start' }]], '图点点击或Enter直接展示所选结果');
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onReference(payload().data.entries[0]); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onConditionsToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, true);
  const nextControl = { getAttribute: name => name === 'aria-label' ? '生产条件下一页' : null, focus: options => focusLog.push(['condition-next', clone(options)]) }, sizeControl = { getAttribute: name => name === 'aria-label' ? '生产条件每页数量' : null, focus: options => focusLog.push(['condition-size', clone(options)]) };
  const conditionRegion = { querySelector: selector => selector.includes('生产条件下一页') ? nextControl : selector.includes('生产条件每页数量') ? sizeControl : null, focus: options => focusLog.push(['condition-pager', clone(options)]) };
  nodes(tree).find(node => node.props['data-decision-history-workspace']).props.ref.current = { getBoundingClientRect: () => ({ height: workspaceHeight }), querySelectorAll: () => [], querySelector: selector => selector === '[data-history-condition-pager]' ? conditionRegion : selector === '[data-history-detail-title]' ? detailTitle : selector === '.dh-chart-keyboard' ? graphFocus : selector.startsWith('[data-dh-row-choice=') ? rowFocus : null };
  local.document.activeElement = nextControl; focusLog.length = 0;
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onQuery({ condition_page: 2 }, true); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert(!nodes(tree).some(node => node.type === local.DecisionHistoryDetails.Details), '分页读取阶段清空旧详情'); assert.deepEqual(focusLog, []); assert.equal(tree.props.style.minHeight, workspaceHeight, '条件分页按同一实测高度保高');
  readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, true); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.data.comparison.conditions.page.number, 2);
  assert.equal(tree.props.style, undefined); assert.deepEqual(focusLog, [['condition-next', { preventScroll: true }]], '新页恢复实际分页按钮焦点，不跳回记录摘要'); assert.equal(requests.at(-1).snapshot_ref, token);
  local.document.activeElement = sizeControl; focusLog.length = 0;
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onQuery({ condition_page: 1, condition_size: 50 }, true); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert(!nodes(tree).some(node => node.type === local.DecisionHistoryDetails.Details)); readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, true); assert.equal(requests.at(-1).condition_page, 1); assert.equal(requests.at(-1).condition_size, 50);
  assert.deepEqual(focusLog, [['condition-size', { preventScroll: true }]], '改每页数量保持展开并恢复数量控件');
  nodes(tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新历史走势').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, true, '同一记录和对照刷新保持展开');
  assert(!('open' in requests.at(-1)) && !('conditionsOpen' in requests.at(-1))); assert.deepEqual(clone(snapshots.at(-1).decision_history_context.detail_queries.conditions), { page: 1, size: 50 }, '展开状态仅在当前Session持有');
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onSelect(payload().data.entries[2], false); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, false, '更换当前记录收起条件');
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onConditionsToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onReference(payload().data.entries[3]); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, false, '更换对照记录收起条件');
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onConditionsToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.onEndComparison(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryDetails.Details).props.conditionsOpen, false, '结束对照收起条件');
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[0], true); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style, undefined, '主动查看不保高');
  readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Table).props.onSelect(payload().data.entries[1], false); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style.minHeight, workspaceHeight);
  readLoading = false; readError = new Error('fixture read failed'); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style, undefined, '读取失败解除保高');
  readError = null; nodes(tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新历史走势').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  workspaceHeight = 1666.25; nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[2], false); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style.minHeight, workspaceHeight, '每次读取重新实测高度');
  nodes(tree).find(node => node.type === 'button' && text(node) === '取消读取').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style, undefined, '取消读取解除保高');
  readLoading = false; nodes(tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新历史走势').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Filters).props.onApply(A.scope({ ...requests.at(-1), order: 'asc' })); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(tree.props.style, undefined, '普通筛选不加保高');
  readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onMissingToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, true);
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[2], true); readLoading = true; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert(!nodes(tree).some(node => node.type === local.DecisionHistoryChart.Chart));
  readLoading = false; tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, true, '同页同指标缺项选择读取后保持展开');
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onSelect(payload().data.entries[4], true); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush();
  nodes(tree).find(node => node.type === 'button' && node.props['aria-label'] === '刷新历史走势').props.onClick(); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, true, '更换缺项记录及刷新保持展开');
  assert(!('missingOpen' in requests.at(-1)) && !('missingOpen' in snapshots.at(-1).decision_history_context), '缺项展开仅由Session持有');
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.MetricControls).props.onMetric(keys[0]); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, false, '更换指标收起缺项');
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onMissingToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  nodes(tree).find(node => node.type === local.DecisionHistoryViews.Filters).props.onApply(A.scope({ ...requests.at(-1), timeline: 'official', selected_entry_ref: null })); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, false, '更换来源收起缺项');
  nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.onMissingToggle(true); tree = state.render(() => local.DecisionHistoryViews.Session(props));
  nodes(tree).find(node => node.type === 'pager').props.onPage(2); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); nodes(tree).find(node => node.type === 'pager').props.onPage(1); tree = state.render(() => local.DecisionHistoryViews.Session(props)); state.flush(); assert.equal(nodes(tree).find(node => node.type === local.DecisionHistoryChart.Chart).props.missingOpen, false, '更换历史页收起缺项');
  const candidate = local.PlanCenterWorkspace({ view: 'gantt', initialContext: origin, onNavigate: (...args) => links.push(args) }); const navigation = expand(nodes(candidate).find(node => node.type === 'candidate-workspace').props.navigation);
  nodes(navigation).find(node => node.type === 'button' && text(node) === '返回历史走势').props.onClick(); assert.deepEqual(clone(links.at(-1)), ['analysis', clone(returned)]);
  nodes(candidate).find(node => node.type === 'candidate-workspace').props.renderTrial({ candidateRef: ref(12), scope: { range_start: windowScope.start, range_end: windowScope.end }, query: '' }).props.onClick();
  assert.equal(links.at(-1)[0], 'trial'); assert.deepEqual(clone(links.at(-1)[1].return_decision_history_context), clone(start)); assert.deepEqual(clone(links.at(-1)[1].base), { candidate_ref: ref(12) });
  const tableState = hooks(), selections = [], table = tableState.render(() => local.DecisionHistoryViews.Table({ data: payload().data, metricKey: keys[0], selectedEntryRef: null, onSelect: row => selections.push(row), onReference() {} }));
  const rows = nodes(table).filter(node => node.props['data-dh-row-choice']); assert.equal(rows.filter(node => node.props.tabIndex === 0).length, 1); nodes(table).find(node => node.props.ref).props.ref.current = { querySelector: () => ({ focus() {} }) }; rows[0].props.onKeyDown({ key: 'End', preventDefault() {} }); assert.equal(selections[0].entry_ref, 'run:' + ref(5));
  const emptyRuntime = runtime(), emptyQueries = [], filteredQuery = A.scope({ metric_keys: keys, timeline: 'official', date_from: '2026-10-12', date_to: '2026-10-12', state: 'success', comparison: 'same_conditions', reference_run_ref: ref(1), range_start: windowScope.start, range_end: windowScope.end, snapshot_ref: token });
  emptyRuntime.window.APSResourceSession = { useQuery: (load, deps) => { const query = JSON.parse(deps[1]); emptyQueries.push(query); const result = payload(query); if (query.date_from) { result.data.entries = []; result.data.trend.points = []; result.data.page.total = 0; result.data.page.has_more = false; result.data.totals = { run: 5, official: 4, filtered: 0 }; } return { loading: false, error: null, result }; } };
  const emptyProps = { adapter: api, start: A.context({ query: filteredQuery, metric_key: keys[1] }), pageContext: {}, onNavigate() {} };
  let emptyTree = emptyRuntime.state.render(() => emptyRuntime.window.DecisionHistoryViews.Session(emptyProps));
  const empty = nodes(emptyTree).find(node => node.type === emptyRuntime.window.ResourceControls.EmptyState && node.props.kind === 'filtered'); assert(empty.props.action, '真实公共filtered必须提供恢复入口'); assert.doesNotThrow(() => expand(empty));
  empty.props.action.props.onClick(); emptyTree = emptyRuntime.state.render(() => emptyRuntime.window.DecisionHistoryViews.Session(emptyProps));
  const restored = emptyQueries.at(-1); assert.equal(restored.date_from, null); assert.equal(restored.date_to, null); assert.equal(restored.state, 'all'); assert.equal(restored.page, 1); assert.equal(restored.snapshot_ref, null);
  for (const key of ['timeline', 'metric_keys', 'range_start', 'range_end', 'reference_run_ref', 'comparison']) assert.deepEqual(clone(restored[key]), clone(filteredQuery[key]), '恢复事件筛选保留 ' + key);
  const outRuntime = runtime(), outQueries = [], outProps = { ...emptyProps, start: A.context({ query: A.scope({ metric_keys: keys, page: 3, snapshot_ref: token }) }) };
  outRuntime.window.APSResourceSession = { useQuery: (load, deps) => { const query = JSON.parse(deps[1]); outQueries.push(query); return { loading: false, error: null, result: payload(query) }; } };
  let outTree = outRuntime.state.render(() => outRuntime.window.DecisionHistoryViews.Session(outProps));
  const out = nodes(outTree).find(node => node.type === outRuntime.window.ResourceControls.EmptyState && node.props.kind === 'filtered'); assert.doesNotThrow(() => expand(out)); assert.equal(text(out.props.action), '返回第 1 页'); out.props.action.props.onClick();
  outTree = outRuntime.state.render(() => outRuntime.window.DecisionHistoryViews.Session(outProps)); assert.equal(outQueries.at(-1).page, 1); assert.equal(outQueries.at(-1).snapshot_ref, token, '超页恢复沿原稳定快照');
  const filterRuntime = runtime(), applied = [], filterQuery = A.scope({ metric_keys: keys, selected_entry_ref: 'run:' + ref(2), reference_run_ref: ref(1), comparison: 'same_conditions', snapshot_ref: token });
  const filterProps = { query: filterQuery, busy: false, onApply: query => applied.push(query) };
  const filters = filterRuntime.state.render(() => filterRuntime.window.DecisionHistoryViews.Filters(filterProps));
  for (const label of ['历史发生起日', '历史发生止日']) assert.equal(nodes(filters).find(node => node.props['aria-label'] === label).props.type, 'date', '日期沿系统原生控件');
  nodes(filters).find(node => node.props['aria-label'] === '历史时间线').props.onChange({ target: { value: 'official' } });
  assert.equal(applied.at(-1).timeline, 'official'); assert.equal(applied.at(-1).selected_entry_ref, null); assert.equal(applied.at(-1).reference_run_ref, ref(1)); assert.equal(applied.at(-1).page, 1); assert.equal(applied.at(-1).snapshot_ref, null);
  const busyFilters = filterRuntime.state.render(() => filterRuntime.window.DecisionHistoryViews.Filters({ ...filterProps, busy: true })), busySource = nodes(busyFilters).find(node => node.props['aria-label'] === '历史时间线');
  assert.equal(Boolean(busySource.props.disabled), false, '读取中来源入口保留焦点'); assert.equal(busySource.props['aria-disabled'], true); busySource.props.onChange({ target: { value: 'run' } }); assert.equal(applied.length, 1, '读取中不重复发起来源查询');
  const metricRuntime = runtime(), metricProps = { query: A.scope({ metric_keys: [keys[0]] }), definitions, metricKey: keys[0], busy: false, onMetric() {}, onQuery() {} };
  let controls = metricRuntime.state.render(() => metricRuntime.window.DecisionHistoryViews.MetricControls(metricProps));
  assert(!nodes(controls).some(node => node.props['aria-label'] === '历史资源时间范围'), '交付指标不铺资源时间表单');
  controls = metricRuntime.state.render(() => metricRuntime.window.DecisionHistoryViews.MetricControls({ ...metricProps, query: filterQuery, metricKey: keys[1] }));
  assert(nodes(controls).some(node => node.props['aria-label'] === '历史资源时间范围'), '资源窗口指标提供统计时间入口');
  for (const key of ['ArrowDown', 'ArrowRight']) { rows[0].props.onKeyDown({ key, preventDefault() {} }); assert.equal(selections.at(-1).entry_ref, 'run:' + ref(2)); }
  for (const key of ['ArrowUp', 'ArrowLeft']) { rows[1].props.onKeyDown({ key, preventDefault() {} }); assert.equal(selections.at(-1).entry_ref, 'run:' + ref(1)); }

}
async function transport() {
  const calls = [], q = A.scope({ metric_keys: keys }), file = { size: 2 }, response = { status: 200, ok: true, headers: { get: key => ({ 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename=history.xlsx', 'X-Workbench-Snapshot-Ref': token, 'X-Workbench-Row-Count': '5' }[key] || null) }, blob: async () => file };
  const api = A.create(async (url, options) => { calls.push({ url, options }); return response; }); const downloaded = await api.historyExport(q, token, 'xlsx', new AbortController().signal, 'all'); assert.equal(downloaded.filename, '排产历史趋势.xlsx'); assert.strictEqual(downloaded.blob, file); assert.equal(downloaded.row_count, 5);
  const url = new URL(calls[0].url, 'http://localhost'); for (const key of ['page', 'size', 'condition_page', 'condition_size']) assert.equal(url.searchParams.has(key), false); assert.equal(url.searchParams.get('snapshot_ref'), token); assert.equal(url.searchParams.get('metric_keys'), keys.join(',')); assert.equal(calls[0].options.method, 'GET');
  await assert.rejects(() => api.historyExport(q, token, 'csv', new AbortController().signal, 'all'));
  const changed = A.create(async () => ({ ...response, headers: { get: key => key === 'X-Workbench-Snapshot-Ref' ? 'changed' : response.headers.get(key) } })); await assert.rejects(() => changed.historyExport(q, token, 'xlsx', new AbortController().signal));
  assert.deepEqual(['run', 'candidate_adoption', 'trial_adoption', 'legacy_official'].map(A.sourceLabel), ['排产运行', '候选方案采用', '试调方案采用', '旧正式计划']);

}
(async () => { queryAndResponse(); chartAndDetails(); navigationAndSession(); await transport(); console.log('Decision history query, chart, saved fields, navigation, snapshot and export contracts passed.'); })().catch(error => { console.error(error); process.exitCode = 1; });
