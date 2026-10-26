'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const app = path.resolve(__dirname, '../../frontend/workbench/app'), window = {};
const context = vm.createContext({ window, AbortController, URLSearchParams, setTimeout, clearTimeout });
for (const name of ['DashboardContract.js', 'RunCandidateAPI.js', 'ResourceProjectionContract.js', 'DashboardAnalysisAPI.js'])
  vm.runInContext(fs.readFileSync(path.join(app, name), 'utf8'), context);
const A = window.DashboardAnalysisAPI, ref = n => String(n).padStart(48, '0'), clone = value => JSON.parse(JSON.stringify(value));
const planRef = ref(1), resourceRef = ref(2), snapshot = 'snapshot_'.padEnd(32, 'a');
const start = '2026-10-17T08:00:00', end = '2026-10-17T10:00:00';
const measures = ['available_hours', 'occupied_hours', 'summed_load_hours', 'outside_calendar_hours', 'overlap_hours',
  'utilization_ratio', 'demand_ratio', 'peak_utilization', 'numerator_hours', 'denominator_hours'];
function summary() {
  return { state: 'complete', issues: [], balance_cv: 0, balance_state: 'complete', balance_reason: null,
    ...Object.fromEntries(measures.map(key => [key, 0])),
    ...Object.fromEntries(['resource_count', 'used_resource_count', 'known_capacity_count', 'unknown_capacity_count',
      'high_pressure_count', 'known_high_pressure_count', 'zero_capacity_task_count', 'conflict_resource_count', 'unknown_day_resource_count'].map(key => [key, 0])) };
}
function metricWindow() {
  return { state: 'complete', source: 'current_transaction_snapshot', metric_version: 'available_occupancy_v1', issues: [],
    ...Object.fromEntries([...measures, 'span_occupied_hours', 'span_summed_hours', 'span_overlap_hours',
      'known_available_hours', 'known_occupied_hours', 'known_summed_load_hours', 'known_utilization_ratio',
      'unknown_days', 'zero_capacity_days', 'task_count', 'operation_count'].map(key => [key, 0])),
    high_pressure: false, zero_capacity_task: false, conflict: false };
}
function task() {
  return { plan_ref: planRef, task_ref: ref(3), operation_ref: ref(4), batch_ref: ref(5), batch_id: 'B-1',
    process_label: '车削', source: 'internal', machine_ref: resourceRef, start, end, span_hours: 2 };
}
function resource(days = []) {
  return { resource_ref: resourceRef, label: '车床', kind: 'machine', state: 'available', days, task_refs: [],
    peak_utilization: 0, zero_capacity_days: 0, unknown_days: 0, window_metrics: metricWindow() };
}
function payload(input = {}) {
  const q = A.scope(input), totals = { tasks: 20000, resources: 2000, downtimes: 600, overlaps: 0,
    deliveries: 643, execution: 20000, pending: 5000, resource_days: 30 };
  const total = ({ overview: 0, delivery: totals.deliveries, actual: totals.execution, downtime: totals.downtimes,
    material: totals.pending, pressure: totals.resources, resource_days: totals.resource_days, timeline: totals.tasks })[q.section];
  const d = { plan: { plan_ref: planRef, kind: 'official', is_current_official: true }, state: 'available',
    time_scope: { range_start: start, range_end: end }, tasks: [], resources: [], downtimes: [], overlaps: [], deliveries: [], execution: [],
    pending: { state: 'available', count: totals.pending, known_count: totals.pending, items: [], issues: [], basis: 'stored_pending_batch_pool' },
    pressure: { threshold: 0.9, known_count: 1200, count: 1200, resource_count: totals.resources, basis: 'same_range_daily_peak_available_occupancy' },
    issues: [], as_of: start, capabilities: { view: true, adopt: false }, basis: 'current_official_plan_and_readiness_sources',
    resource_common: { metric_version: 'decision-resource-v4', source: 'current_transaction_snapshot', start, end,
      time_basis: 'factory_local', cohort_basis: 'current_official_plan', cohort: [], machine: summary(), operator: summary() },
    pagination: { section: q.section, number: q.page, size: q.size, total, pages: Math.max(1, Math.ceil(total / q.size)), totals } };
  const length = Math.min(q.size, Math.max(0, total - (q.page - 1) * q.size));
  for (let i = 0; i < length; i++) {
    if (q.section === 'delivery') d.deliveries.push({ batch_ref: ref(100 + i), batch_id: 'B-' + i, risk: 'on_time' });
    if (q.section === 'material') d.pending.items.push({ batch_ref: ref(100 + i), batch_id: 'P-' + i,
      stored_status: 'pending', quantity: 10, readiness_issues: [] });
    if (q.section === 'pressure') d.resources.push({ ...resource(), resource_ref: ref(100 + i) });
    if (q.section === 'timeline') d.tasks.push({ ...task(), task_ref: ref(100 + i) });
  }
  if (q.section === 'timeline' && length) d.deliveries.push({ batch_ref: ref(5), batch_id: 'B-1', risk: 'on_time' });
  if (q.section === 'resource_days') d.resources.push(resource(Array.from({ length }, () => ({ date: start.slice(0, 10), start, end,
    available_hours: 8, occupied_hours: 2, inside_available_hours: 2, outside_available_hours: 0, overlap_hours: 0, utilization: 0.25,
    window_metrics: metricWindow() }))));
  return { ok: true, schema_version: 1, data: d, meta: { request_ref: 'a'.repeat(32), source: 'production',
    time_basis: 'factory_local', snapshot_ref: q.snapshot_ref || snapshot, as_of: start }, warnings: [] };
}
function rejected(value, query, mutate) {
  const changed = clone(value); mutate(changed); assert.throws(() => A.validate(changed, planRef, query));
}
function pagesAndTotals() {
  const overviewQuery = { section: 'overview', page: 1, size: 20 }, overview = payload(overviewQuery);
  assert.strictEqual(A.validate(overview, planRef, overviewQuery), overview.data);
  assert.equal(overview.data.pending.known_count, 5000, '总待排数保留完整统计，首页无需携带全部批次');
  assert.equal(overview.data.pending.items.length, 0); assert.equal(overview.data.pressure.resource_count, 2000);
  for (const section of ['delivery', 'timeline', 'material', 'pressure']) {
    const query = { section, page: 2, size: 1, snapshot_ref: snapshot }, value = payload(query);
    assert.strictEqual(A.validate(value, planRef, query), value.data, section + ' 的小页与全局总数应同时有效');
    rejected(value, query, changed => { changed.meta.snapshot_ref = 'b'.repeat(32); });
    rejected(value, query, changed => { changed.data.pagination.number = 1; });
    rejected(value, query, changed => { changed.data.pagination.size = 2; });
  }
  const deliveryQuery = { section: 'delivery', page: 2, size: 1 }, delivery = payload(deliveryQuery);
  rejected(delivery, deliveryQuery, changed => { changed.data.tasks = [task()]; });
  assert.throws(() => A.validate(delivery, planRef, { ...deliveryQuery, section: 'timeline' }), '不同分析分组的页不能混用');
  rejected(overview, overviewQuery, changed => { changed.data.tasks = [task()]; });
  rejected(overview, overviewQuery, changed => { changed.data.pending.known_count = 0; changed.data.pending.count = 0; });
  rejected(overview, overviewQuery, changed => { changed.data.pressure.resource_count = 0; });
  const material = payload({ section: 'material', size: 1 });
  rejected(material, { section: 'material', size: 1 }, changed => { changed.data.pending.items = []; });
  const daysQuery = { section: 'resource_days', page: 2, size: 1, resource_ref: resourceRef }, days = payload(daysQuery);
  assert.strictEqual(A.validate(days, planRef, daysQuery), days.data);
  rejected(days, daysQuery, changed => { changed.data.resources[0].resource_ref = ref(999); });
  const emptyQuery = { section: 'delivery', page: 1000, size: 1 };
  assert.equal(A.validate(payload(emptyQuery), planRef, emptyQuery).deliveries.length, 0, '超出总页数时保留真实空页');
  const locateQuery = { section: 'timeline', page: 1, size: 1, locate_batch_ref: ref(5), snapshot_ref: snapshot };
  const located = payload({ ...locateQuery, page: 37 });
  assert.strictEqual(A.validate(located, planRef, locateQuery), located.data, '批次定位解析原时间轴页号，不把全局工序范围缩为所选批次');
  assert.equal(located.data.pagination.total, 20000);
  rejected(located, locateQuery, changed => { changed.data.tasks[0].batch_ref = ref(6); });
  rejected(located, locateQuery, changed => { changed.data.tasks[0].source = 'external'; });
  rejected(located, locateQuery, changed => { changed.data.pagination.number = 20001; });
}
function catalogSummary() {
  const C = window.DashboardContract, query = C.scope({}), scope = { kind: 'dashboard', ...query }; delete scope.page;
  const value = payload({ section: 'overview' }), categories = Object.fromEntries(Object.keys(C.categories).slice(1).map(key =>
    [key, { state: key === 'candidate' ? 'unavailable' : 'no_data', risk_count: key === 'candidate' ? null : 0,
      known_risk_count: 0, unknown_count: 0, issues: [], evaluation_gaps: [] }]));
  Object.assign(categories.external, { kind: 'outsourcing_receipts',
    tracking_basis: 'manual_receipt_facts', handling_supported: true, handling_count: 0, closed_count: 0,
    entry: { view: 'outsourcing', target: '/api/workbench/v1/outsourcing/receipts', enabled: true },
    ...Object.fromEntries(['receipt_count', 'current_receipt_count', 'awaiting_return_count', 'overdue_count', 'returned_count',
      'awaiting_confirmation_count', 'unregistered_count', 'source_gap_count'].map(key => [key, 0])) });
  value.data = { categories, items: [], scope, as_of: value.meta.as_of, plan: value.data.plan,
    page: { number: 1, size: query.size, total: 0, pages: 1 }, candidate_catalog: { state: 'unavailable', runs: [] },
    resource_pressure: { resource_count: 2000, plan_ref: planRef, detail_target: '/api/workbench/v1/dashboard/analysis?section=pressure',
      time_scope: { range_start: start, range_end: end, time_basis: 'factory_local', boundary: 'half_open' } } };
  assert.strictEqual(C.catalog(value, query), value, '值班台主清单使用资源总数和详情入口，无需携带资源明细');
  const bundled = clone(value); bundled.data.resource_pressure.resources = [];
  assert.throws(() => C.catalog(bundled, query), '主清单拒绝重新捆绑资源明细');
}
async function transport() {
  const calls = [], api = A.create(async (url, options) => {
    calls.push({ url, options }); const params = new URL(url, 'http://localhost').searchParams;
    const query = Object.fromEntries(params); delete query.plan_ref; query.page = Number(query.page); query.size = Number(query.size);
    return { status: 200, ok: true, headers: { get: () => 'application/json' }, json: async () => payload(query) };
  });
  const query = { section: 'resource_days', page: 2, size: 1, snapshot_ref: snapshot, resource_ref: resourceRef };
  await api.read(planRef, new AbortController().signal, query);
  const url = new URL(calls[0].url, 'http://localhost');
  assert.equal(url.pathname, '/api/workbench/v1/dashboard/analysis'); assert.equal(url.searchParams.get('plan_ref'), planRef);
  for (const [key, value] of Object.entries(query)) assert.equal(url.searchParams.get(key), String(value));
  assert.equal(calls[0].options.method, 'GET');
  await api.read(planRef); assert.equal(new URL(calls[1].url, 'http://localhost').searchParams.get('section'), 'delivery');
  await api.read(planRef, undefined, { section: 'timeline', locate_batch_ref: ref(5) });
  assert.equal(new URL(calls[2].url, 'http://localhost').searchParams.get('locate_batch_ref'), ref(5));
  const before = calls.length;
  for (const invalid of [{ section: 'unknown' }, { page: 0 }, { size: 101 }, { extra: true },
    { snapshot_ref: 'stale' }, { section: 'resource_days' }, { resource_ref: resourceRef },
    { locate_batch_ref: ref(5) }, { section: 'timeline', locate_batch_ref: 'invalid' }])
    await assert.rejects(() => api.read(planRef, undefined, invalid));
  assert.equal(calls.length, before, '无效分页与资源范围在发送请求前拒绝');
  const mismatched = A.create(async () => ({ status: 200, ok: true, headers: { get: () => 'application/json' },
    json: async () => payload({ section: 'delivery', page: 1, size: 1, snapshot_ref: 'b'.repeat(32) }) }));
  await assert.rejects(() => mismatched.read(planRef, undefined, { section: 'delivery', page: 1, size: 1, snapshot_ref: snapshot }), /已更新/);
}
(async () => { pagesAndTotals(); catalogSummary(); await transport(); console.log('Dashboard analysis pagination, complete totals, section and snapshot contracts passed.'); })()
  .catch(error => { console.error(error); process.exitCode = 1; });
