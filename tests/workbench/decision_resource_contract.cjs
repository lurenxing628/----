'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const { compile } = require('../../scripts/workbench/compile.cjs');
const root = path.resolve(__dirname, '../..'), app = path.join(root, 'frontend/workbench/app');
const ref = n => n.toString(16).padStart(48, '0'), run = ref(1), chosen = ref(2), baseline = ref(3), official = ref(4), token = 's'.repeat(32);
const machines = Array.from({ length: 23 }, (_, i) => ref(i + 100)), operators = [ref(200), ref(201)], outside = ref(999);
const start = '2026-12-01T00:00:00', end = '2027-01-01T00:00:00';
const dates = Array.from({ length: 31 }, (_, i) => '2026-12-' + String(i + 1).padStart(2, '0'));
const clone = value => JSON.parse(JSON.stringify(value));
const h = (type, props, ...children) => ({ type, props: props || {}, children: children.flat(Infinity).filter(value => value !== null && value !== false && value !== undefined) });
const nodes = node => !node || typeof node !== 'object' ? [] : [node, ...node.children.flatMap(nodes)];
const text = node => node == null ? '' : typeof node !== 'object' ? String(node) : node.children.map(text).join(' ');
function expand(node) { if (!node || typeof node !== 'object') return node; if (typeof node.type === 'function') return expand(node.type({ ...node.props, children: node.children })); return { ...node, children: node.children.map(expand) }; }
function hooks() {
  let cursor = 0; const slots = [], effects = [], same = (a, b) => a && b && a.length === b.length && a.every((value, i) => value === b[i]);
  return { React: { createElement: h, Fragment: 'fragment', useRef(initial) { const i = cursor++; if (!slots[i]) slots[i] = { current: initial }; return slots[i]; },
    useState(initial) { const i = cursor++; if (!slots[i]) slots[i] = { value: typeof initial === 'function' ? initial() : initial }; return [slots[i].value, update => { slots[i].value = typeof update === 'function' ? update(slots[i].value) : update; }]; },
    useMemo(make, deps) { const i = cursor++; if (!slots[i] || !same(slots[i].deps, deps)) slots[i] = { deps, value: make() }; return slots[i].value; },
    useEffect(effect, deps) { const i = cursor++, prior = slots[i]; if (!prior || !same(prior.deps, deps)) { slots[i] = { deps, cleanup: prior && prior.cleanup }; effects.push(() => { if (slots[i].cleanup) slots[i].cleanup(); slots[i].cleanup = effect(); }); } },
    useReducer(reducer, initial) { const [value, set] = this.useState(initial); return [value, action => set(old => reducer(old, action))]; } },
    render(fn) { cursor = 0; return fn(); }, reset() { slots.length = 0; effects.length = 0; }, flush() { while (effects.length) effects.shift()(); } };
}
const sources = ['resource-contract.js', 'resource-session.js', 'WorkbenchFormat.js', 'WorkbenchTerms.js', 'RunGenerationContract.js', 'WorkbenchDatePickerModel.js', 'ResourceProjectionContract.js', 'EffortProjectionContract.js', 'PlanGanttModel.js', 'RunCandidateModel.js', 'RunCandidateAPI.js', 'RecommendationContract.js', 'RunDecisionAPI.js', 'RunDecisionRecommendation.jsx', 'RunDecisionComparison.jsx', 'RunDecisionResources.jsx', 'RunDecisionResourceHeatmap.jsx'];
const built = compile({ babel_path: path.join(root, 'frontend/workbench/prototype/ui_kits/workbench/assets/vendor/babel-7.29.0.min.js'), sources: sources.map(name => ({ path: name, code: fs.readFileSync(path.join(app, name), 'utf8') })) }).outputs;
function runtime(state = hooks()) {
  const window = { ResourceControls: { Button: 'button', Modal: 'modal' }, WorkbenchReference: 'reference', PointContract: {},
    RunCandidateControls: { Button: 'button', Pager: 'pager', ErrorBox: 'error-box', Reasons: 'reasons' } };
  for (const output of built) vm.runInNewContext(output.code, { React: state.React, window, AbortController, DOMException, setTimeout, clearTimeout, URLSearchParams });
  return { window, state };
}
const { window } = runtime(), API = window.RunDecisionAPI, R = window.RunDecisionResources;
const common = { selected_candidate_ref: chosen, reference_candidate_ref: baseline, resource_view: 'selected_batches', range_start: start, range_end: end };
function scope(q) { return { run_ref: run, selected_candidate_ref: chosen, comparison_mode: q.comparison_mode || 'candidates', resource_view: q.resource_view || 'selected_batches', range_start: start, range_end: end,
  resource_refs: { machine: q.resource_view === 'full_candidate' ? [...machines, outside] : machines, operator: operators }, reference_state: 'available',
  reference: q.comparison_mode === 'admission_official' ? { kind: 'admission_official', baseline_ref: official } : { kind: 'candidate', candidate_ref: baseline } }; }
function metricWindow(extra = {}) { return { state: 'complete', calendar_state: 'complete', actual_work_state: 'not_recorded', source: 'archived_resource_calendar', metric_version: 'decision-resource-v4', issues: [], reservation_overlaps: [], reservations: [], contribution_operation_count: 2, known_contribution_operation_count: 2,
  available_hours: 8, occupied_hours: 4, summed_load_hours: 6, outside_calendar_hours: 1, overlap_hours: 2,
  span_occupied_hours: 5, span_summed_hours: 7, span_overlap_hours: 2, overlap_span_hours: 2,
  utilization_ratio: 0.5, demand_ratio: 0.75, peak_utilization: 0.9, high_pressure: true, zero_capacity_task: false, zero_capacity_reason: null, conflict: true, demand_overload: false, daily_peak_utilization: 0.9, high_pressure_period_count: 1, high_pressure_periods: [],
  unknown_days: 0, zero_capacity_days: 0, task_count: 2, operation_count: 2, known_available_hours: 8, known_occupied_hours: 4, known_summed_load_hours: 6,
  known_utilization_ratio: 0.5, numerator_hours: 4, denominator_hours: 8, ...extra }; }
function summary() { return { ...metricWindow(), resource_count: 23, used_resource_count: 20, known_capacity_count: 23, unknown_capacity_count: 0,
  high_pressure_count: 3, known_high_pressure_count: 3, zero_capacity_task_count: 0, conflict_resource_count: 2, unknown_day_resource_count: 0,
  balance_cv: 0.5, balance_state: 'complete', balance_reason: null }; }
const deltas = { available_hours: 0, occupied_hours: 1, summed_load_hours: 2, outside_calendar_hours: 1, overlap_hours: 1, utilization_ratio: 0.125, peak_utilization: 0.25, demand_ratio: 0.25, balance_cv: 0.1 };
const coverage = { formal_state: 'available', formal_operation_count: 2, covered_formal_operation_count: 2, missing_formal_operation_refs: [], formal_coverage_complete: true, unplanned_operation_refs: [], deferred_operation_refs: [], missing_formal_arrangements: [] };
function drill(q, resource, side = 'selected') { const formal = side === 'reference' && q.comparison_mode === 'admission_official'; return { run_ref: run, candidate_ref: side === 'reference' && !formal ? baseline : chosen,
  comparison_mode: q.comparison_mode || 'candidates', resource_view: q.resource_view || 'selected_batches', resource_kind: q.resource_kind || 'machine', resource_ref: resource, range_start: start, range_end: end,
  ...(formal ? { reference_view: true, plan_ref: official } : {}) }; }
function day(q, resource, date) { const tasks = side => [{ row_ref: ref(500), operation_ref: ref(501), batch_ref: ref(502), batch_label: 'B-1', process_label: '车削', start: date + 'T08:00:00', end: date + 'T12:00:00', occupied_hours: 4, span_hours: 4, locked: false, drill: drill(q, resource, side) }];
  return { date, grain: q.grain, placeholder: null, key: date, bucket_key: date, group_key: date, start: date + 'T00:00:00', end: date === dates.at(-1) ? '2027-01-01T00:00:00' : '2026-12-' + String(Number(date.slice(-2)) + 1).padStart(2, '0') + 'T00:00:00', before: metricWindow({ tasks: tasks('reference'), conflicts: [] }), after: metricWindow({ tasks: tasks('selected'), conflicts: [] }), deltas: clone(deltas), drill: { selected: drill(q, resource), reference: drill(q, resource, 'reference') } }; }
function payload(q = {}, section = 'resources') {
  q = { ...common, ...q }; if (q.comparison_mode === 'admission_official') delete q.reference_candidate_ref; q = API.resourceScope(run, q, section); const s = scope(q), refs = s.resource_refs[q.resource_kind].filter(value => !q.resource_ref || value === q.resource_ref);
  const envelope = { ok: true, schema_version: 1, warnings: [], meta: { request_ref: '1'.repeat(32), source: 'production', time_basis: 'factory_local', snapshot_ref: token, as_of: end } };
  const base = { run_ref: run, scope: s, candidate: { candidate_ref: chosen, label: '所选候选' }, baseline: q.comparison_mode === 'admission_official' ? { kind: 'admission_official', baseline_ref: official, label: '受理时正式计划 v1', state: 'available' } : { kind: 'candidate', candidate_ref: baseline, label: '候选基准', state: 'available' },
    filters: { section, resource_kind: q.resource_kind, resource_ref: q.resource_ref || null, grain: q.grain, pressure_threshold: q.pressure_threshold, display_start: q.display_start || null, display_end: q.display_end || null, bucket_start: q.bucket_start || null, bucket_end: q.bucket_end || null }, coverage: { before: clone(coverage), after: clone(coverage) }, metric_version: 'decision-resource-v4' };
  if (section === 'resource-days') {
    const values = q.bucket_start ? [{ ...day(q, q.resource_ref, q.bucket_start.slice(0, 10)), start: q.bucket_start, end: q.bucket_end }] : dates.slice((q.page - 1) * q.size, q.page * q.size).map(date => day(q, q.resource_ref, date));
    return { ...envelope, data: { ...base, resource: { ref: q.resource_ref, label: '资源1', kind: q.resource_kind }, items: values, display_scope: { start: values[0].start, end: values.at(-1).end }, page: { number: q.page, size: q.size, total: q.bucket_start ? 1 : dates.length, has_more: q.bucket_start ? false : q.page * q.size < dates.length }, summary: { before: metricWindow(), after: metricWindow() } } };
  }
  const rows = refs.map(resource => ({ resource_ref: resource, resource_kind: q.resource_kind, label: '资源' + resource.slice(-3), before: metricWindow(), after: metricWindow(), filter_summary: { high_pressure_period_count: 1, demand_overload_period_count: 0, conflict_period_count: 0, period_peak_utilization: 0.9, daily_peak_utilization: 0.9, high_pressure_periods: [] }, deltas: clone(deltas), drill: { selected: drill(q, resource), reference: drill(q, resource, 'reference') } }));
  const items = rows.slice((q.page - 1) * q.size, q.page * q.size), visibleDates = dates.slice((q.heatmap_page - 1) * q.heatmap_size, q.heatmap_page * q.heatmap_size), buckets = visibleDates.map(date => { const cell = day(q, refs[0], date); return { key: date, date, label: date, start: cell.start, end: cell.end }; }), display = { start: buckets[0].start, end: buckets.at(-1).end };
  return { ...envelope, data: { ...base, filters: { ...base.filters, ...(q.grain === 'hour' ? { display_start: display.start, display_end: display.end } : {}), pressure_filter: q.pressure_filter, sort: q.sort, order: q.order }, items,
    filter_options: { resources: [...s.resource_refs.machine.map(ref => ({ ref, label: '设备', kind: 'machine' })), ...s.resource_refs.operator.map(ref => ({ ref, label: '人员', kind: 'operator' }))] }, page: { number: q.page, size: q.size, total: refs.length, has_more: q.page * q.size < refs.length },
    summary: { before: summary(), after: summary(), deltas: clone(deltas) }, rankings: { top_pressure: rows.slice(0, 10), top_increase: rows.slice(0, 10), limit: 10, total: rows.length },
    pressure_scope: { basis: q.grain === 'hour' ? 'displayed_hours' : 'full_resource_window', grain: q.grain, threshold: q.pressure_threshold, ...(q.grain === 'hour' ? display : { start, end }) }, heatmap: { grain: q.grain, window_scope: { basis: 'full_resource_window', start, end }, focus_scope: { basis: q.grain === 'hour' ? 'hour_focus' : 'full_resource_window', start, end }, display_scope: { basis: 'displayed_periods', ...display }, buckets, page: { number: q.heatmap_page, size: q.heatmap_size, total: dates.length, has_more: q.heatmap_page * q.heatmap_size < dates.length }, items: items.map(row => ({ resource_ref: row.resource_ref, resource_kind: row.resource_kind, label: row.label, continuations: [], cells: visibleDates.map(date => day(q, row.resource_ref, date)) })) } } };
}
function rejected(value, modify, query = common, section = 'resources') { const changed = clone(value); modify(changed); assert.throws(() => API.resourceDetails(changed, run, query, section)); }
function identityContracts() {
  const value = payload(); assert.strictEqual(API.resourceDetails(value, run, common), value.data);
  assert.equal(value.data.items[0].after.metric_version, 'decision-resource-v4', '时段资源明细采用同一v4资源投影');
  rejected(value, result => { result.data.metric_version = 'decision-resource-v3'; });
  rejected(value, result => { result.data.scope.resource_view = 'full_candidate'; });
  rejected(value, result => { result.data.items[0].after.source = 'current_transaction_snapshot'; });
  rejected(value, result => { result.data.heatmap.items.reverse(); });
  rejected(value, result => { result.data.heatmap.items[0].cells[0].date = dates[1]; });
  rejected(value, result => { result.data.items[0].drill.reference.candidate_ref = chosen; });
  rejected(value, result => { result.data.scope.resource_refs.machine = [outside]; }, { ...common, expected_resource_refs: scope(common).resource_refs });
  const officialQuery = { ...common, comparison_mode: 'admission_official' }; delete officialQuery.reference_candidate_ref;
  const formal = payload(officialQuery); assert.equal(API.resourceDetails(formal, run, officialQuery).items[0].drill.reference.reference_view, true);
  rejected(formal, result => { result.data.items[0].drill.reference.plan_ref = baseline; }, officialQuery);
  for (const kind of ['machine', 'operator']) { const q = { ...common, resource_kind: kind, resource_ref: scope(common).resource_refs[kind][0] }, days = payload(q, 'resource-days');
    assert.equal(API.resourceDetails(days, run, q, 'resource-days').resource.kind, kind);
    rejected(days, result => { result.data.items[0].before.tasks[0].drill.candidate_ref = chosen; }, q, 'resource-days'); }
  for (const wrong of [{ selected_candidate_ref: undefined }, { resource_kind: 'batch' }, { size: 7 }, { heatmap_size: 20 }]) assert.throws(() => API.resourceScope(run, { ...common, ...wrong }));
  assert.throws(() => API.resourceScope(run, common, 'resource-days'), /请选择/);
  const saved = { resource_kind: 'machine', resource_ref: outside, page: 2, snapshot_ref: token, grain: 'hour',
    display_start: '2026-11-30T23:00:00', display_end: '2026-12-01T01:00:00', heatmap_page: 2, sort: 'label', pressure_threshold: 0.8 };
  assert.deepEqual(clone(API.savedResourceView(saved, scope(common).resource_refs, scope(common))),
    { resource_kind: 'machine', page: 1, grain: 'hour', heatmap_page: 1, sort: 'label', pressure_threshold: 0.8 },
    '越界资源和显示窗按同一规则清理，同时保留有效筛选');
  const boundary = { grain: 'hour', display_start: start + '.000000', display_end: end + '.000000', snapshot_ref: token, heatmap_page: 2 };
  assert.deepEqual(clone(API.savedResourceView(boundary, scope(common).resource_refs, scope(common))), boundary,
    '资源显示窗的等价零小数边界仍在当前比较范围内，保留原快照与页码');
}
function presentationContracts() {
  const zero = metricWindow({ state: 'complete', available_hours: 0, utilization_ratio: null, demand_ratio: null, peak_utilization: null, zero_capacity_task: false, high_pressure: false, conflict: false }), unknown = metricWindow({ state: 'unavailable', available_hours: null, utilization_ratio: null, demand_ratio: null, peak_utilization: null });
  for (const field of ['utilization_ratio', 'demand_ratio', 'peak_utilization']) { assert.equal(R.metricState(zero, field), 'not_applicable'); assert(R.metricText(zero, field).includes('不适用')); assert.equal(R.metricText(unknown, field), '未知'); }
  assert.equal(R.metricText({ ...summary(), balance_cv: null, balance_state: 'not_applicable', balance_reason: { message: '全部资源无安排。' } }, 'balance_cv'), '不适用');
  const absent = payload().data; absent.baseline.state = 'absent'; absent.summary.before.available_hours = 184;
  const missingBasis = expand(h(R.Summary, { data: absent })), beforeCells = nodes(missingBasis).filter(node => node.type === 'tr')[1].children;
  assert(text(beforeCells[1]).includes('184'), '正式基准缺失仍显示归档班表的已知容量');
  assert(text(beforeCells[2]).includes('比较基准缺失'), '缺比较对象的占用继续表达基准缺失');
  const missing = payload().data; missing.coverage.after.missing_formal_operation_refs = [ref(501)];
  missing.coverage.after.missing_formal_arrangements = [{ operation_ref: ref(501), row_ref: ref(500), batch_ref: ref(502), batch_label: 'B-旧计划', process_label: '车削', start, end }];
  const missingText = text(expand(h(R.Coverage, { data: missing }))).replace(/\s+/g, ' ');
  assert(missingText.includes('B-旧计划 · 车削'), '缺失正式安排沿接口实际批次和工序名称展示');
  assert(!missingText.includes('未知 车削'), '未提供的工序序号不制造未知值');
  for (const [state, mode, reason] of [['absent', 'admission_official', '排产时尚无正式计划。'], ['selection_required', 'candidates', '选定比较基准后显示差值。']]) {
    const noBaseline = clone(missing); noBaseline.baseline.state = state; noBaseline.scope.comparison_mode = mode;
    noBaseline.coverage.before.unplanned_operation_refs = [ref(501), ref(502)]; noBaseline.coverage.before.deferred_operation_refs = [ref(503)];
    noBaseline.coverage.after.unplanned_operation_refs = [ref(504)]; noBaseline.coverage.after.deferred_operation_refs = [ref(505)];
    const coverageTree = expand(h(R.Coverage, { data: noBaseline }));
    const sideText = label => text(nodes(coverageTree).find(node => node.type === 'div' && node.children.some(child => child && child.type === 'strong' && text(child).replace(/\s/g, '') === label + '：'))).replace(/\s+/g, ' ');
    const before = sideText('基准'), after = sideText('当前方案');
    assert(before.includes(reason) && before.includes('待确认'), '缺基准说明缺对象和覆盖状态');
    assert(!before.includes(window.WorkbenchTerms.missing_arrangements(2, 1)) && !before.includes('B-旧计划'), '缺对象不冒充已知空计划或已知未安排数量');
    assert(after.includes(window.WorkbenchTerms.missing_arrangements(1, 1)) && after.includes('B-旧计划 · 车削'), '所选侧保持真实未安排、缺料和缺失正式记录');
  }
  const segmented = payload({ resource_ref: machines[0] }, 'resource-days'); segmented.data.items[0].after.tasks.push({ ...segmented.data.items[0].after.tasks[0], row_ref: ref(506) });
  const dailyTree = expand(h(R.Days, { result: segmented, query: common, adapter: {}, onQuery() {}, onClose() {} }));
  assert(nodes(dailyTree).some(node => node.type === 'summary' && text(node).replace(/\s/g, '').includes('当前方案：2段安排记录')), '同工序多段列表按实际安排记录段数展示');
  const data = payload().data; let presentationReads = 0; Object.defineProperty(data.heatmap.items[0].cells[0], 'after', { get() { presentationReads++; return zero; } });
  const selection = [], focus = [], { state, window: local } = runtime();
  let tree = state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data, focus: { resource_ref: machines[0], date: dates[0], bucket_key: dates[0] }, mode: 'after', onCursor: value => selection.push(value), onFocus: (...args) => focus.push(args) }));
  const buttons = nodes(tree).filter(node => node.props['data-heatmap-row'] !== undefined);
  assert.equal(buttons.filter(node => node.props.tabIndex === 0).length, 1, '热图只有当前日格进入 Tab 顺序');
  assert.equal(buttons[0].props['data-value-state'], 'not_applicable'); assert.equal(text(buttons[0]), '休息'); assert.equal(buttons[0].props['data-conflict'], undefined, '跨夜休息不显示加工冲突'); assert.equal(buttons[0].props['data-zero-capacity'], undefined, '跨夜保留跨度不显示零容量工作警报');
  assert(buttons[0].props['aria-label'].includes('2026-12-01') && buttons[0].props['aria-label'].includes('当前方案：可排 0 小时'));
  const target = { focus: options => selection.push(options), scrollIntoView: () => selection.push('scroll'), getBoundingClientRect: () => ({ top: 581, left: 500 }) }, frame = nodes(tree).find(node => node.props.ref);
  frame.props.ref.current = { scrollTop: 31, scrollLeft: 0, clientTop: 0, clientLeft: 0, getBoundingClientRect: () => ({ top: 581, left: 281 }), querySelector: selector => { if (selector === 'thead th.wb-col-key') return { getBoundingClientRect: () => ({ height: 28, width: 180 }) }; selection.push(selector); return target; } };
  buttons[0].props.onKeyDown({ key: 'ArrowRight', preventDefault() {} }); assert.equal(selection.at(-1).date, dates[1]); assert.equal(focus.length, 0, '方向键移动焦点不触发单资源读请求');
  assert.equal(frame.props.ref.current.scrollTop, 3, '实际首格被28px固定表头遮挡时，热图滚动使其完整可见');
  assert.equal(selection.find(value => value && value.preventScroll === true).preventScroll, true, '先定位焦点再由热图职责处理滚动');
  buttons[0].props.onClick(); assert.equal(focus[0][0].resource_ref, machines[0]); assert.equal(focus[0][1].date, dates[0]);
  const preparedPresentationReads = presentationReads;
  state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data, focus: { resource_ref: machines[0], bucket_key: dates[1] }, mode: 'after', onCursor() {}, onFocus() {} }));
  assert.equal(presentationReads, preparedPresentationReads, 'Moving the heatmap cursor reuses bucket presentation facts');
  state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data, mode: 'after', definitions: [{ key: 'machine_high_pressure_count', label: '新的负荷定义' }], onCursor() {}, onFocus() {} }));
  assert(presentationReads > preparedPresentationReads, 'A changed metric definition rebuilds its affected presentation');
  const sideData = payload().data, compared = sideData.heatmap.items[0].cells[0];
  compared.after = metricWindow({ utilization_ratio: 1, occupied_hours: 8, high_pressure: true, zero_capacity_task: true, demand_overload: true, conflict: true });
  compared.before = metricWindow({ utilization_ratio: 0.852, occupied_hours: 6.816, high_pressure: false, zero_capacity_task: null, demand_overload: false, conflict: false }); compared.deltas.utilization_ratio = 0.148;
  for (const mode of ['after', 'before', 'delta']) {
    const modeTree = state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data: { ...sideData, heatmap: { ...sideData.heatmap } }, mode, onCursor() {}, onFocus() {} })), cell = nodes(modeTree).find(node => node.props['data-heatmap-row'] === 0 && node.props['data-heatmap-column'] === 0);
    assert.equal(cell.props['aria-label'], cell.props.title, '提示与读屏共享当前侧的数值和告警');
    for (const flag of ['data-pressure', 'data-zero-capacity', 'data-conflict']) assert.equal(cell.props[flag], mode === 'after' ? true : undefined, '颜色标记沿显示侧使用明确为真的告警');
    if (mode === 'before') {
      assert(text(cell).includes('85.2%') && cell.props.title.includes('固定对照：可排 8 小时，班表内占用 6.816 小时'), '固定对照显示自己的占用与容量');
      assert.equal(text(cell), '85.2%', '已知正常日格只突出数值，未知零容量依据留在提示'); assert(cell.props.title.includes('无可排时段工作是否发生待确认'));
      for (const warning of ['高负荷设备', '无可排时段仍有工作', '需求超载', '班表内冲突']) assert(!cell.props.title.includes(warning), '固定对照不继承查看方案的告警:' + warning);
    } else if (mode === 'delta') {
      assert(cell.props.title.includes('当前方案：高负荷设备') && cell.props.title.includes('当前方案：需求超载') && cell.props.title.includes('当前方案：班表内冲突'), '差值格保留告警事实所属侧');
      assert(cell.props.title.includes('固定对照：可排 8 小时，班表内占用 6.816 小时'), '差值提示分别标注两侧事实');
      assert(cell.props.title.includes('固定对照：无可排时段工作是否发生待确认') && !text(cell).includes('待确认'), '差值保留所属侧的未知依据，主格只突出明确警报');
    }
  }
  compared.before = metricWindow({ state: 'partial', calendar_state: 'unavailable', available_hours: 0, utilization_ratio: null, high_pressure: null, zero_capacity_task: null, demand_overload: null, conflict: null });
  const pendingTree = state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data: sideData, mode: 'before', onCursor() {}, onFocus() {} })), pendingCell = nodes(pendingTree).find(node => node.props['data-heatmap-row'] === 0 && node.props['data-heatmap-column'] === 0);
  assert.equal(pendingCell.props['data-pressure'], undefined); assert.equal(pendingCell.props['data-zero-capacity'], undefined); assert.equal(pendingCell.props['data-conflict'], undefined);
  assert.equal(text(pendingCell), '待确认'); assert.equal(pendingCell.props['data-value-state'], 'unknown'); assert.equal(compared.before.zero_capacity_task, null, '零容量的安排状态未知继续与已知休息分开');
  assert(pendingCell.props.title.includes('高负荷设备待确认') && pendingCell.props.title.includes('无可排时段工作是否发生待确认') && pendingCell.props.title.includes('需求超载待确认') && pendingCell.props.title.includes('班表内冲突待确认'), '零容量与未知标记保留待确认状态');
  const preservedRest = { ...zero, calendar_state: 'complete', actual_work_state: 'not_recorded', occupied_hours: 0, zero_capacity_task: null, outside_calendar_hours: 24, span_occupied_hours: 24, overlap_hours: 0 }, savedRest = clone(preservedRest);
  compared.before = clone(preservedRest); compared.after = clone(preservedRest);
  for (const mode of ['before', 'after']) {
    const restTree = state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data: { ...sideData, heatmap: { ...sideData.heatmap } }, mode, onCursor() {}, onFocus() {} })), restCell = nodes(restTree).find(node => node.props['data-heatmap-row'] === 0 && node.props['data-heatmap-column'] === 0);
    assert.equal(text(restCell), '休息'); assert.equal(restCell.props['data-value-state'], 'not_applicable'); assert.equal(restCell.props['data-zero-capacity'], undefined); assert.equal(restCell.props['data-conflict'], undefined);
    assert(restCell.props['aria-label'].includes('无可排时段工作是否发生待确认'), '已确认休息的24小时保留跨度不升级成未知班表，实际工作缺项继续保留读屏提示');
    assert.equal(compared[mode].utilization_ratio, null, '无容量不补成0%'); assert.deepEqual(clone(compared[mode]), savedRest, '两侧原始未知工作信号及保留跨度全部保持');
  }
  compared.before = { ...zero, zero_capacity_task: true };
  const occupiedZero = local.RunDecisionResourceHeatmap.cellPresentation(sideData.heatmap.items[0], compared, 'before');
  assert.equal(occupiedZero.text, '无可排时段仍有工作'); assert.equal(occupiedZero.zeroCapacity, true);
  compared.before = metricWindow({ utilization_ratio: 0, occupied_hours: 0, high_pressure: false, conflict: false });
  assert.equal(local.RunDecisionResourceHeatmap.cellText(compared, 'before'), '0.0%', '真实空闲显示0，不归入休息或未知');
  for (const secondStart of [dates[0] + 'T18:30:00', dates[1] + 'T00:00:00', dates[1] + 'T00:30:00']) {
    const shiftEnvelope = payload({ grain: 'shift' }), shiftData = shiftEnvelope.data, firstCell = shiftData.heatmap.items[0].cells[0];
    firstCell.start = dates[0] + 'T06:30:00'; firstCell.end = dates[0] + 'T10:30:00';
    shiftData.heatmap.items[0].cells.splice(1, 0, { ...clone(firstCell), bucket_key: dates[0] + '-night', start: secondStart, end: dates[1] + 'T02:30:00' });
    shiftData.heatmap.items[0].continuations.push({ group_key: dates[1], bucket_key: dates[0] + '-night', date: dates[0], start: secondStart, end: dates[1] + 'T02:30:00', continuation_start: secondStart > dates[1] + 'T00:00:00' ? secondStart : dates[1] + 'T00:00:00', continuation_end: dates[1] + 'T02:30:00', basis: 'continuation_of_archived_work_period' });
    assert.equal(API.resourceDetails(shiftEnvelope, run, { ...common, grain: 'shift' }), shiftData);
    const nightFocus = [], shiftTree = state.render(() => local.RunDecisionResourceHeatmap.Heatmap({ data: shiftData, mode: 'after', onCursor() {}, onFocus: (...values) => nightFocus.push(values) }));
    const shiftButtons = nodes(shiftTree).filter(node => node.props['data-heatmap-row'] === 0 && node.props['data-resource-date'] === dates[0]);
    assert.equal(shiftButtons.length, 2, '同资源同日真实多班段保持独立格');
    assert(shiftButtons[0].props['aria-label'].includes('06:30') && shiftButtons[1].props['aria-label'].includes('02:30'), '班次按钮沿真实归档边界与跨夜结束展示');
    const continuation = nodes(shiftTree).find(node => node.props['data-resource-continuation']);
    assert(continuation && text(continuation).includes('班段延续'), '续日格使用说明链接，保留原完整夜班的一次计时');
    continuation.props.onClick(); assert.equal(nightFocus[0][1].start, secondStart); assert.equal(nightFocus[0][1].end, dates[1] + 'T02:30:00', '延续链接读取原完整班段');
  }
  const preciseQuery = { ...common, resource_ref: machines[0], grain: 'hour', bucket_start: dates[0] + 'T08:00:00', bucket_end: dates[0] + 'T09:00:00' }, preciseResult = payload(preciseQuery, 'resource-days');
  preciseResult.data.items[0].after.tasks[0].occupied_hours = 0.125;
  state.reset();
  const preciseTree = state.render(() => expand(h(local.RunDecisionResources.SelectedWindow, { result: preciseResult, query: preciseQuery, adapter: {}, onClose() {}, onWhole() {} })));
  assert(text(preciseTree).includes('0.125'), '时段贡献使用共同接口保存数值，页面不以安排跨度重算工时');
  const revealState = hooks(), { window: revealWindow } = runtime(revealState), revealed = [], revealProps = { result: preciseResult, query: preciseQuery, adapter: {}, onClose() {}, onWhole() {} };
  const revealTree = revealState.render(() => revealWindow.RunDecisionResources.SelectedWindow(revealProps));
  nodes(revealTree).find(node => node.type === 'h3').props.ref.current = { focus: options => revealed.push(['focus', options]), scrollIntoView: options => revealed.push(['scroll', options]) };
  revealState.flush(); assert.equal(revealed[0][0], 'focus'); assert.equal(revealed[0][1].preventScroll, true); assert.equal(revealed[1][1].block, 'start', '主动查看资源后从顶栏下方展示标题、关键数值及原因');
  revealState.render(() => revealWindow.RunDecisionResources.SelectedWindow({ ...revealProps, query: { ...preciseQuery, focus_date: dates[1] } })); revealState.flush();
  assert.equal(revealed.length, 2, '单纯矩阵浏览呈现状态变化不重复拉到明细标题');
  preciseResult.data.items[0].after.contribution_operation_count = null; preciseResult.data.items[0].after.known_contribution_operation_count = 1;
  const partialTree = state.render(() => expand(h(local.RunDecisionResources.SelectedWindow, { result: preciseResult, query: preciseQuery, adapter: {}, onClose() {}, onWhole() {} })));
  const partialText = text(partialTree).replace(/\s+/g, ' ');
  assert(partialText.includes('未知') && partialText.includes('已知小计 1'), '缺项贡献工序数保留未知与真实已知小计');
  const wholeResult = payload({ ...common, resource_ref: machines[0] }, 'resource-days'), wholeDrills = [];
  Object.assign(wholeResult.data.summary.after, { occupied_hours: 6.75, utilization_ratio: 0.84375 });
  const wholeTree = state.render(() => expand(h(local.RunDecisionResources.SelectedWindow, { result: wholeResult, query: common, whole: true, adapter: {}, onQuery() {}, onClose() {}, onDrill: value => wholeDrills.push(value) })));
  assert(text(wholeTree).includes('整个统计范围') && nodes(wholeTree).some(node => node.props.className === 'rres-contribution-row'), '资源整窗在同一邻近详情直接显示贡献，逐日宽表按需展开');
  const wholeSummary = nodes(wholeTree).find(node => node.props.className === 'rres-contribution-summary');
  assert(text(wholeSummary).includes('6.75') && text(wholeSummary).includes('84.4%'), '整个范围摘要直接取summary，独立于本页首格和贡献列表');
  assert(text(wholeTree).includes('以下为本页日期范围') && text(wholeTree).includes(window.WorkbenchFormat.compactRange(wholeResult.data.display_scope.start, wholeResult.data.display_scope.end)), '本页日期标签沿响应display_scope');
  nodes(wholeTree).find(node => node.props['data-resource-batch']).props.onClick();
  assert.equal(wholeDrills[0].batch_ref, ref(502)); assert.equal(wholeDrills[0].operation_ref, undefined, '批次入口读取当前贡献批次，并清除单工序定位');
  const narrowed = R.storedQuery({ resource_ref: machines[0], day_resource_ref: machines[0], day_bucket_start: start, day_bucket_end: dates[0] + 'T23:59:59', day_snapshot_ref: token, heatmap_focus: { resource_ref: machines[0], bucket_key: dates[0] } }, scope(common).resource_refs, { range_start: dates[1] + 'T00:00:00', range_end: end });
  assert.equal(narrowed.day_bucket_start, undefined); assert.equal(narrowed.day_snapshot_ref, undefined); assert.equal(narrowed.resource_ref, machines[0], '收窄共同窗口清旧时段，保留有效永久资源选择');
  const retained = R.storedQuery({ resource_kind: 'machine', resource_ref: outside, day_resource_ref: outside, page: 2, day_page: 2, snapshot_ref: token, day_snapshot_ref: token, heatmap_focus: { resource_ref: outside, date: dates[0] } }, scope(common).resource_refs);
  assert.equal(retained.resource_ref, undefined); assert.equal(retained.day_resource_ref, undefined); assert.equal(retained.snapshot_ref, undefined); assert.equal(retained.page, 1);
  assert.equal(R.storedQuery({ resource_ref: machines[0], day_resource_ref: machines[0] }, scope(common).resource_refs).day_resource_ref, machines[0], 'cohort 收缩仍保留有效资源选择');
  assert.equal(window.RunCandidateModel.resourceMatches({ machine: { ref: machines[0] }, operator: { ref: operators[1] } }, { kind: 'operator', ref: operators[0] }), false, '甘特使用实际种类和永久身份过滤安排');
  const rangeState = hooks(), { window: rangeWindow } = runtime(rangeState), ranges = [], returns = [];
  const rangeProps = { scope: { range_start: '2026-12-01T08:00:00.123456', range_end: '2026-12-02T18:00:00.654321' }, title: '统计时间', onRange: value => ranges.push(value) };
  let rangeTree = rangeState.render(() => rangeWindow.RunDecisionResources.RangeControls(rangeProps)); rangeState.flush();
  assert(!nodes(rangeTree).some(node => node.type === 'form'), '统计时间默认只保留紧凑入口');
  nodes(rangeTree).find(node => node.props.ref).props.ref.current = { querySelector: () => ({ focus: options => returns.push(options) }) };
  nodes(rangeTree).find(node => node.props['data-resource-range-entry']).props.onClick();
  rangeTree = rangeState.render(() => rangeWindow.RunDecisionResources.RangeControls(rangeProps));
  assert.equal(nodes(rangeTree).find(node => node.props['aria-label'] === '统计时间开始').props.value, '2026-12-01 08:00:00.123456', '编辑显示使用系统格式并保留秒和小数');
  nodes(rangeTree).find(node => node.type === 'form').props.onSubmit({ preventDefault() {} });
  rangeTree = rangeState.render(() => rangeWindow.RunDecisionResources.RangeControls(rangeProps));
  assert.deepEqual(clone(ranges[0]), rangeProps.scope); assert.equal(returns.length, 1); assert.equal(returns[0].preventScroll, true);
  assert(!nodes(rangeTree).some(node => node.type === 'form'), '应用统计时间后收起表单并将焦点还入口');
}
const turns = async () => { for (let i = 0; i < 8; i++) await Promise.resolve(); };
async function paneContracts() {
  const { state, window: local } = runtime(), calls = [], daily = [], signals = [];
  const overview = { data: { run: { run_ref: run }, scope: scope(common) }, meta: { snapshot_ref: token } }, props = { result: overview, query: {}, onQuery: next => { props.query = next; }, onView: () => {},
    adapter: { resources: async (run, q, signal) => { calls.push(clone(q)); signals.push(signal); if (calls.length === 1) throw new Error('首读失败'); return payload(q); }, resourceDays: async (run, q) => { daily.push(clone(q)); return payload(q, 'resource-days'); } } };
  let tree; async function render() { for (let i = 0; i < 3; i++) { tree = state.render(() => local.RunDecisionResources.Pane(props)); state.flush(); await turns(); } }
  await render(); assert.equal(calls.length, 1); assert(nodes(tree).some(node => node.type === 'error-box' && node.props.error));
  assert.equal(calls[0].heatmap_size, 7, '默认使用后端已有合法7时段，保持用户显式页大小');
  nodes(tree).find(node => node.props['aria-label'] === '刷新资源影响').props.onClick(); await render(); assert.equal(calls.length, 2, '资源首读失败可刷新重试');
  nodes(tree).find(node => node.type === 'pager' && node.props.label === '资源影响').props.onPage(2); await render(); assert.equal(calls.at(-1).page, 2); assert.equal(calls.at(-1).snapshot_ref, token);
  const map = nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap);
  map.props.onPage(2); await render(); assert.equal(calls.at(-1).heatmap_page, 2); assert.equal(calls.at(-1).snapshot_ref, token);
  const nextMap = nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap), before = calls.length;
  nextMap.props.onCursor({ resource_ref: machines[20], date: dates[14] }); await render(); assert.equal(calls.length, before, '日格焦点变化不重读资源');
  nextMap.props.onFocus({ resource_ref: machines[20] }, { date: dates[24], bucket_key: dates[24], start: dates[24] + 'T00:00:00', end: dates[24] + 'T23:59:59' }, 10); await render(); assert.equal(daily.at(-1).bucket_start, dates[24] + 'T00:00:00', '点击时段读取精确起止范围，独立绑定明细快照'); assert.equal(daily.at(-1).bucket_end, dates[24] + 'T23:59:59');
  const loadedResources = calls.length, loadedDays = daily.length;
  props.enabled = false; await render(); props.enabled = true; await render();
  assert.equal(calls.length, loadedResources); assert.equal(daily.length, loadedDays, '同上层快照重开资源与逐日面板复用各自成功读取');
  props.enabled = false; props.result = { ...overview, meta: { snapshot_ref: 't'.repeat(32) } }; await render();
  assert.equal(calls.length, loadedResources); assert.equal(daily.length, loadedDays, '隐藏资源面板随上层快照失效而不提前读取');
  props.enabled = true; await render();
  assert.equal(calls.length, loadedResources + 1); assert.equal(daily.length, loadedDays + 1, '重开刷新后的资源与逐日面板各读当前身份一次');
  const visibleQuery = clone(props.query), hiddenQuery = { ...props.query, resource_ref: outside }, normalized = [];
  props.enabled = false; props.query = hiddenQuery; props.onQuery = next => { normalized.push(next); props.query = next; }; await render();
  assert.equal(normalized.length, 0, '隐藏资源面板不回写查询规范化');
  props.query = visibleQuery; props.onQuery = next => { props.query = next; }; props.enabled = true; await render();
  console.log(JSON.stringify({ r18_resources: { same_snapshot_reopen: { resources: 0, days: 0 }, hidden_refresh: { resources: 0, days: 0 }, refreshed_reopen: { resources: 1, days: 1 }, hidden_query_updates: normalized.length } }));
  const remembered = clone(props.query.heatmap_focus), focusEvents = [], readsBeforeClose = calls.length, detailsBeforeClose = daily.length;
  const selectedCell = { dataset: { resourceRef: machines[20], resourceBucket: dates[24] }, focus: options => { focusEvents.push(['cell', options]); nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap).props.onCursor(remembered); }, scrollIntoView: options => focusEvents.push(['scroll', options]) };
  const resourceEntry = { dataset: { resourceEntry: machines[20] }, focus: options => focusEvents.push(['entry', options]), scrollIntoView: options => focusEvents.push(['scroll', options]) };
  const pane = nodes(tree).find(node => node.props['aria-label'] === '资源使用对照'); let currentCells = [selectedCell];
  pane.props.ref.current = { querySelectorAll: selector => selector === '.rres-day-cell' ? currentCells : [resourceEntry], querySelector: () => null };
  nodes(tree).find(node => node.type === local.RunDecisionResources.SelectedWindow).props.onClose(); await render();
  assert.equal(focusEvents[0][0], 'cell'); assert.equal(focusEvents[0][1].preventScroll, true, '关闭时段明细恢复原热力图时段焦点');
  assert.equal(props.query.day_resource_ref, undefined, '焦点回写后关闭状态仍保持明细清除'); assert.equal(props.query.heatmap_focus.bucket_key, dates[24]);
  assert.equal(calls.length, readsBeforeClose); assert.equal(daily.length, detailsBeforeClose, '恢复焦点只更新呈现，不重读资源或时段明细');
  nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap).props.onFocus({ resource_ref: machines[20] }, { date: dates[24], bucket_key: dates[24], start: dates[24] + 'T00:00:00', end: dates[24] + 'T23:59:59' }); await render();
  nodes(tree).find(node => node.type === local.RunDecisionResources.SelectedWindow).props.onWhole(); await render();
  const expandedRange = nodes(tree).find(node => node.type === local.RunDecisionResources.SelectedWindow);
  assert.equal(expandedRange.props.whole, true); assert.equal(expandedRange.props.result.data.resource.ref, machines[20]);
  assert.equal(daily.at(-1).bucket_start, undefined); assert.equal(daily.at(-1).grain, 'day', '时段→整个范围仍在同一邻近详情，清除精确bucket并保留资源');
  expandedRange.props.onClose(); await render();
  nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap).props.onFocus({ resource_ref: machines[20] }); await render(); currentCells = []; focusEvents.length = 0;
  const wholePanel = nodes(tree).find(node => node.type === local.RunDecisionResources.SelectedWindow);
  assert.equal(wholePanel.props.whole, true, '资源名复用精确时段的同一详情组件'); wholePanel.props.onClose(); await render();
  assert.equal(focusEvents[0][0], 'entry', '原时段已退出 DOM 时关闭明细回到同一资源入口'); assert.equal(props.query.day_resource_ref, undefined);
  props.query = { ...props.query, resource_ref: machines[0] }; await render();
  nodes(tree).find(node => node.type === 'button' && text(node) === '人员').props.onClick(); await render();
  assert.equal(calls.at(-1).resource_kind, 'operator'); assert.equal(calls.at(-1).resource_ref, undefined); assert.equal(props.query.day_resource_ref, undefined);
  assert.equal(calls.at(-1).snapshot_ref, undefined, '资源类别和筛选变化刷新业务快照');
  nodes(tree).find(node => node.props['aria-label'] === '资源影响排序').props.onChange({ target: { value: 'label' } }); await render(); assert.equal(calls.at(-1).page, 1);
  nodes(tree).find(node => node.type === 'button' && text(node) === '小时').props.onClick(); await render(); assert.equal(calls.at(-1).grain, 'hour');
  const hourMap = nodes(tree).find(node => node.type === local.RunDecisionResourceHeatmap.Heatmap);
  hourMap.props.onPage(2); await render(); assert.equal(calls.at(-1).snapshot_ref, undefined, '小时换页改变筛选显示范围，刷新事实快照'); assert.equal(calls.at(-1).page, 1);
  nodes(tree).find(node => node.props['aria-label'] === '资源高负荷关注线').props.onChange({ target: { value: '0.8' } }); await render(); assert.equal(calls.at(-1).pressure_threshold, 0.8);

  props.query = { ...props.query, resource_kind: 'machine', resource_ref: outside, day_resource_ref: outside, heatmap_focus: { resource_ref: outside, date: dates[0] } };
  await render(); assert.equal(calls.at(-1).resource_ref, undefined); assert.equal(props.query.day_resource_ref, undefined, 'view/cohort 收缩不继续读取已退出范围的资源');
  props.adapter.resources = (run, q, signal) => { calls.push(clone(q)); signals.push(signal); return new Promise(() => {}); };
  nodes(tree).find(node => node.props['aria-label'] === '刷新资源影响').props.onClick(); await render();
  nodes(tree).find(node => node.type === 'button' && text(node) === '取消读取').props.onClick(); await render(); assert(signals.at(-1).aborted);

  // The real Pane consumes the combined response inside its existing read owner.
  const seeded = runtime(), resourceCalls = [], normalizedQueries = [];
  const combined = query => ({ ...overview, resource_query: API.resourceFilters(query), resource_result: payload(query) });
  const seedProps = { result: combined({}), query: {}, onQuery: next => { normalizedQueries.push(clone(next)); seedProps.query = next; }, onView() {},
    adapter: { resources: async (_, q) => { resourceCalls.push(clone(q)); return payload(q); }, resourceDays: async (_, q) => payload(q, 'resource-days') } };
  let seededTree;
  async function seedRender() { for (let index = 0; index < 3; index++) { seededTree = seeded.state.render(() => seeded.window.RunDecisionResources.Pane(seedProps)); seeded.state.flush(); await turns(); } }
  await seedRender(); assert.equal(resourceCalls.length, 0, '组合首屏直接消费资源 envelope，不再发单独 resources 请求');
  assert(nodes(seededTree).some(node => node.type === seeded.window.RunDecisionResources.Summary));
  assert.equal(seedProps.query.snapshot_ref, undefined, '新签发资源 token 不回写叶查询');
  seedProps.enabled = false; await seedRender(); seedProps.enabled = true; await seedRender();
  assert.equal(resourceCalls.length, 0, '成功首屏隐藏重开复用现有读结果');
  nodes(seededTree).find(node => node.props['aria-label'] === '刷新资源影响').props.onClick(); await seedRender();
  assert.equal(resourceCalls.length, 1, '已消费组合响应后的明确刷新发一次真实资源请求');
  nodes(seededTree).find(node => node.type === 'pager' && node.props.label === '资源影响').props.onPage(2); await seedRender();
  assert.equal(resourceCalls.length, 2); assert.equal(resourceCalls.at(-1).page, 2); assert.equal(resourceCalls.at(-1).snapshot_ref, token);
  nodes(seededTree).find(node => node.props['aria-label'] === '资源高负荷关注线').props.onChange({ target: { value: '0.8' } }); await seedRender();
  assert.equal(resourceCalls.length, 3); assert.equal(resourceCalls.at(-1).pressure_threshold, 0.8); assert.equal(resourceCalls.at(-1).snapshot_ref, undefined);
  seedProps.result = combined(seedProps.query); await seedRender();
  assert.equal(resourceCalls.length, 3, '同 token 的新父响应按原对象身份消费一次');
  seedProps.enabled = false; seedProps.result = combined(seedProps.query); await seedRender();
  assert.equal(resourceCalls.length, 3, '隐藏的新组合响应等待显示');
  seedProps.enabled = true; await seedRender(); assert.equal(resourceCalls.length, 3, '显示后消费新父响应无需额外请求');
  seedProps.query = { resource_ref: outside, page: 2, snapshot_ref: token };
  seedProps.result = combined({ page: 1 }); const beforeNormalization = normalizedQueries.length; await seedRender();
  assert.equal(normalizedQueries.length, beforeNormalization + 1); assert.equal(resourceCalls.length, 3, '有效叶筛选回写稳定 canonical query，不触发第三次读取');
  assert.equal(seedProps.query.resource_ref, undefined); assert.equal(seedProps.query.snapshot_ref, undefined);
  const rejection = { ok: false, committed: false, status: 409, error: { code: 'snapshot_stale', message: '资源保存身份已变化。', fields: [], retryable: false, request_ref: '1'.repeat(32) } };
  seedProps.result = { ...combined(seedProps.query), resource_result: rejection }; await seedRender();
  const error = nodes(seededTree).find(node => node.type === 'error-box' && node.props.error).props.error;
  assert.equal(error.code, rejection.error.code); assert.equal(error.status, 409); assert.equal(error.committed, false); assert.equal(resourceCalls.length, 3);
  seedProps.enabled = false; await seedRender(); seedProps.enabled = true; await seedRender();
  assert.equal(resourceCalls.length, 4, '组合中的明确资源失败由原 hook 在重开时重试真实 resources 一次');
  console.log(JSON.stringify({ u5_resource_workspace_reads: { first_combined_resource_http: 0, same_result_reopen: 0, refresh: 1, page: 1, threshold: 1,
    new_parent_same_token_extra_http: 0, hidden_new_parent_extra_http: 0, normalized_query_extra_http: 0, explicit_failure_reopen: 1, new_token_query_updates: 0 } }));
}
async function transportContracts() {
  const calls = [], responses = [], transport = API.create(async (url, options) => { calls.push({ url: new URL(url, 'http://localhost'), options }); return responses.shift(); });
  const json = value => ({ ok: true, headers: { get: key => key === 'Content-Type' ? 'application/json' : null }, json: async () => value });
  const q = { ...common, page: 2, heatmap_page: 2, heatmap_size: 7, snapshot_ref: token, expected_resource_refs: scope(common).resource_refs };
  responses.push(json(payload(q))); await transport.resources(run, q); assert.equal(calls.at(-1).url.searchParams.has('expected_resource_refs'), false);
  assert.equal(calls.at(-1).url.searchParams.get('heatmap_page'), '2');
  const download = { ok: true, headers: { get: key => ({ 'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Content-Disposition': 'attachment; filename=decision.xlsx', 'X-Workbench-Run-Ref': run, 'X-Workbench-Snapshot-Ref': token, 'X-Workbench-Row-Count': '23' })[key] || null }, blob: async () => new Blob(['fixture']) };
  for (const section of ['resources', 'resource-days']) {
    const exportedQuery = { ...q, resource_ref: machines[0], filter_section: section }; responses.push(download); await transport.decisionExport(run, exportedQuery, token, 'xlsx', undefined, 'all');
    const params = calls.at(-1).url.searchParams; assert.equal(params.get('filter_section'), section); assert.equal(params.get('resource_ref'), machines[0]); assert.equal(params.get('resource_view'), 'selected_batches');
    for (const key of ['page', 'size', 'heatmap_page', 'heatmap_size']) assert.equal(params.has(key), false, '导出所有页删除显示分页:' + key);
  }
  const hourExport = { ...common, grain: 'hour', display_start: '2026-12-01T08:00:00.125', display_end: '2026-12-01T15:00:00.125', pressure_threshold: 0.8, pressure_filter: 'high_pressure', heatmap_page: 2, heatmap_size: 7 };
  responses.push(download); await transport.decisionExport(run, hourExport, token, 'xlsx', undefined, 'resources');
  assert.equal(calls.at(-1).url.searchParams.get('display_start'), hourExport.display_start, '小时筛选导出保服务给出的真实当前显示窗与精度');
  assert.equal(calls.at(-1).url.searchParams.get('display_end'), hourExport.display_end); assert.equal(calls.at(-1).url.searchParams.get('pressure_threshold'), '0.8');
  const bucketExport = { ...common, resource_ref: machines[0], grain: 'shift', bucket_start: '2026-12-01T18:30:00.125', bucket_end: '2026-12-02T02:30:00.125' };
  responses.push(download); await transport.decisionExport(run, bucketExport, token, 'xlsx', undefined, 'resource-days');
  assert.equal(calls.at(-1).url.searchParams.get('bucket_start'), bucketExport.bucket_start, '精确班次导出绑定选择时段');
  assert.equal(calls.at(-1).url.searchParams.get('bucket_end'), bucketExport.bucket_end);
}
async function main() { identityContracts(); presentationContracts(); await paneContracts(); await transportContracts(); console.log('decision resource contract: common cohort/calendar identity, correct-side drill, zero/unknown ratio, heatmap keyboard and day focus, kind/view reset, snapshot paging/export and cancellation passed'); }
main().catch(error => { console.error(error); process.exitCode = 1; });
