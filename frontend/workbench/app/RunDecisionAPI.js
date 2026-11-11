import RunCandidateAPI from './RunCandidateAPI.js';
import RunGenerationContract from './RunGenerationContract.js';
import APSWorkbenchTransport from './shared/network/transport.js';
import { equal } from './shared/session/pending-store.js';
import WorkbenchTerms from './WorkbenchTerms.js';

const A = RunCandidateAPI, G = RunGenerationContract, T = APSWorkbenchTransport, { check, ref, time, timeKey } = A;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const queryKeys = ['selected_candidate_ref', 'reference_candidate_ref', 'comparison_mode', 'resource_view', 'range_start', 'range_end', 'snapshot_ref'];
function bindSnapshot(payload, query) {
  if (query.snapshot_ref) check(payload.meta.snapshot_ref === query.snapshot_ref, '比较资料已更新，请刷新后重试。');
}
function bindScope(payload, data, query) {
  bindSnapshot(payload, query);
  check(data.scope.resource_view === query.resource_view, '资源统计范围已变化，请刷新。');
  for (const key of ['range_start', 'range_end']) if (query[key])
    check(time(data.scope[key]) && timeKey(data.scope[key]) === timeKey(query[key]), '比较时间范围已变化，请刷新。');
  if (query.comparison_mode === 'admission_official')
    check(data.scope.reference && data.scope.reference.kind === 'admission_official' && data.baseline && data.baseline.kind === 'admission_official'
      && data.baseline.baseline_ref === data.scope.reference.baseline_ref && data.baseline.state === data.scope.reference_state,
    '比较基准的正式计划资料已变化，请刷新。');
}
// 各 *Scope 只保留填了值的筛选（空串、null、undefined 都不进 q）；后端把未填的筛选回显为 null，比较时用 `?? null` 对齐。
function scope(runRef, query) {
  check(ref(runRef), '请从排产记录打开方案对比。');
  const value = { comparison_mode: 'candidates', resource_view: 'selected_batches' };
  queryKeys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
  check(['candidates', 'admission_official'].includes(value.comparison_mode), '请选择本次排产的方案或排产时的正式计划进行比较。');
  check(['selected_batches', 'full_candidate'].includes(value.resource_view), '请选择资源统计范围。');
  check(value.comparison_mode !== 'admission_official' || value.reference_candidate_ref === undefined, '比较方式与比较基准不匹配，请从排产记录重新打开方案对比。');
  ['selected_candidate_ref', 'reference_candidate_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '方案选择已失效，请重新选择。'));
  if (value.range_start !== undefined || value.range_end !== undefined)
    check(time(value.range_start) && time(value.range_end) && value.range_start < value.range_end, '请同时填写开始和结束时间，结束须晚于开始。');
  return value;
}
function _decisionCore(payload, runRef, q) {
  const data = payload.data;
  check(object(data.run) && data.run.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef
    && data.scope.comparison_mode === q.comparison_mode && Array.isArray(data.candidates), '比较资料与当前排产记录不一致，请点“刷新方案对比”。');
  const candidates = new Set(data.candidates.map(row => row && row.candidate_ref));
  check(data.scope.selected_candidate_ref === null || candidates.has(data.scope.selected_candidate_ref), '当前查看方案已不在这次排产中，请点“刷新方案对比”。');
  if (q.selected_candidate_ref) check(data.scope.selected_candidate_ref === q.selected_candidate_ref, '当前查看方案已变化，请点“刷新方案对比”。');
  if (q.comparison_mode === 'candidates' && data.scope.reference_state === 'available') check(data.scope.reference && candidates.has(data.scope.reference.candidate_ref), '比较基准已不在这次排产中，请点“刷新方案对比”。');
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref) check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '比较基准已变化，请点“刷新方案对比”。');
  if (q.comparison_mode === 'admission_official') check(data.scope.reference && data.scope.reference.kind === 'admission_official', '比较基准的正式计划资料已变化，请点“刷新方案对比”。');
  bindScope(payload, data, q);
  return data;
}
function _validateDecisionSummary(payload, runRef, q) {
  const data = _decisionCore(payload, runRef, q), baseline = data.baseline;
  check(object(baseline) && baseline.state === data.scope.reference_state
    && (data.scope.comparison_mode !== 'candidates' || (data.scope.reference_state === 'selection_required' ? baseline.candidate_ref === null : baseline.candidate_ref === data.scope.reference.candidate_ref)),
    '方案首屏指标或基准资料不完整，请点“刷新方案对比”。');
  return data;
}
const completionFilters = ['all', 'complete', 'unfinished', 'ordinary', 'deferred', 'unknown'];
function completionScope(runRef, query) {
  const value = { ...scope(runRef, query), completion_filter: 'all', sort: 'batch_id', order: 'asc', page: 1, size: 20 };
  ['completion_filter', 'sort', 'order', 'page', 'size'].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref(value.selected_candidate_ref), '请选择要查看批次安排的方案。');
  check(completionFilters.includes(value.completion_filter) && value.sort === 'batch_id' && ['asc', 'desc'].includes(value.order), '批次安排的筛选或排序条件无效，请重新选择。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '批次清单每页支持 20 或 50 条，请重新选择页码。');
  return value;
}
function _validateCompletionBatches(payload, runRef, q) {
  const data = payload.data;
  check(data.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef
    && data.scope.selected_candidate_ref === q.selected_candidate_ref && data.scope.comparison_mode === q.comparison_mode
    && object(data.candidate) && data.candidate.candidate_ref === q.selected_candidate_ref
    && object(data.source) && data.source.candidate_ref === q.selected_candidate_ref
    && object(data.filters) && data.filters.section === 'completion-batches'
    && ['completion_filter', 'sort', 'order'].every(key => data.filters[key] === q[key])
    && object(data.page) && data.page.number === q.page && data.page.size === q.size,
  '批次安排资料与当前方案或比较范围不一致，请刷新批次清单。');
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
    check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '批次安排的比较基准已变化，请刷新批次清单。');
  bindScope(payload, data, q);
  return data;
}
function processScope(runRef, query) {
  const value = { ...scope(runRef, query), record_kind: 'attempts', order: 'asc', page: 1, size: 20 };
  ['process_candidate_ref', 'objective', 'record_kind', 'sort', 'order', 'page', 'size'].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  if (value.process_candidate_ref === undefined && value.selected_candidate_ref) value.process_candidate_ref = value.selected_candidate_ref;
  if (value.sort === undefined) value.sort = value.record_kind === 'progress' ? 'elapsed_ms' : 'rank';
  check(value.process_candidate_ref === undefined || ref(value.process_candidate_ref), '优化过程的方案选择已失效，请重新选择方案。');
  check(value.objective === undefined || G.objective(value.objective), '请选择有效的优化方向。');
  check(['attempts', 'progress'].includes(value.record_kind)
    && (value.record_kind === 'progress' ? ['event_index', 'elapsed_ms', 'primary_value'] : ['rank', 'elapsed_ms']).includes(value.sort)
    && ['asc', 'desc'].includes(value.order), '优化过程的筛选或排序条件无效，请重新选择。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '优化过程每页支持 20 或 50 条，请重新选择页码。');
  return value;
}
function _processDetails(payload, runRef, q) {
  const data = payload.data;
  check(data.run_ref === runRef && data.capture_ref === runRef
    && object(data.scope) && data.scope.run_ref === runRef && data.scope.comparison_mode === q.comparison_mode
    && (q.selected_candidate_ref === undefined || data.scope.selected_candidate_ref === q.selected_candidate_ref),
  '共同优化过程的运行或保存选项不一致，请点“刷新优化过程”。');
  bindScope(payload, data, q);
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
    check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '过程的查看基准已变化，请点“刷新优化过程”。');
  check(object(data.selected_objective) && (q.objective === undefined || data.selected_objective.name === q.objective),
    '过程的优化方向或评分字段已变化，请点“刷新优化过程”。');
  const anchor = data.candidate && data.candidate.candidate_ref;
  check(ref(anchor) && (q.process_candidate_ref === undefined || anchor === q.process_candidate_ref),
    '过程来源定位已变化，请点“刷新优化过程”。');
  check(object(data.filters) && data.filters.section === 'process'
    && data.filters.process_candidate_ref === anchor && data.filters.objective === data.selected_objective.name
    && ['record_kind', 'sort', 'order'].every(key => data.filters[key] === q[key])
    && object(data.page) && data.page.number === q.page && data.page.size === q.size,
  '过程方向、来源或分页位置已变化，请点“刷新优化过程”。');
  return data;
}
function detailScope(runRef, query, section) {
  const value = { ...scope(runRef, query), page: 1, size: 20, change_kind: 'all', sort: section === 'batches' ? 'worsened' : 'sequence', order: section === 'batches' ? 'desc' : 'asc' };
  if (section === 'batches') value.delivery_filter = 'all';
  ['page', 'size', 'change_kind', 'sort', 'order', 'batch_ref', ...(section === 'operations' ? ['resource_ref'] : ['delivery_filter', 'selected_batch_ref'])].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref(value.selected_candidate_ref), '请选择需要查看的方案。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '明细每页支持 20 或 50 条，请重新选择页码。');
  if (value.sort === 'current_priority' && query.order === undefined) value.order = 'asc';
  ['batch_ref', 'resource_ref', 'selected_batch_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '明细的批次或资源选择已失效，请重新选择。'));
  if (section === 'batches') check(['all', 'attention', 'overdue', 'deferred', 'unplanned', 'on_time'].includes(value.delivery_filter), '请选择需要查看的交付问题。');
  return value;
}
function _details(payload, runRef, q, section) {
  const data = payload.data;
  check(data.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
    && data.scope.comparison_mode === q.comparison_mode && object(data.candidate) && data.candidate.candidate_ref === q.selected_candidate_ref
    && object(data.page) && data.page.number === q.page && data.page.size === q.size && object(data.filters) && data.filters.section === section,
  '明细的方案、比较范围或页码已变化，请点“刷新影响明细”。');
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
    check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '明细的比较基准已变化，请点“刷新影响明细”。');
  ['change_kind', 'sort', 'order'].forEach(key => check(data.filters[key] === q[key], '明细的筛选或排序已变化，请点“刷新影响明细”。'));
  ['batch_ref', ...(section === 'operations' ? ['resource_ref'] : [])].forEach(key => check(data.filters[key] === (q[key] ?? null), '明细的批次或资源已变化，请点“刷新影响明细”。'));
  if (section === 'batches') {
    if (data.filters.delivery_filter !== undefined) check(data.filters.delivery_filter === q.delivery_filter, '交付问题筛选已变化，请点“刷新影响明细”。');
    if (q.selected_batch_ref || data.filters.selected_batch_ref !== undefined) check(data.filters.selected_batch_ref === (q.selected_batch_ref ?? null)
      && (q.selected_batch_ref ? data.selected_batch && data.selected_batch.batch_ref === q.selected_batch_ref : data.selected_batch === null),
    '所选批次与当前方案的归档资料不一致，请点“刷新影响明细”。');
  }
  bindScope(payload, data, q);
  return data;
}
const preparationSorts = ['sequence', 'batch_id', 'after_setup_hours', 'after_required_hours', 'setup_delta_hours'];
const changeoverSorts = ['next_start', 'machine_label', 'next_batch_id'];
function preparationScope(runRef, query, section = 'preparation') {
  check(['preparation', 'changeovers'].includes(section), '请选择准备需求或工种切换明细。');
  const value = { ...scope(runRef, query), page: 1, size: 20, sort: section === 'preparation' ? 'sequence' : 'next_start', order: 'asc',
    ...(section === 'preparation' ? { allocation_state: 'all', work_scope: 'all' } : { event_side: 'all' }) };
  ['page', 'size', 'sort', 'order', 'machine_ref', ...(section === 'preparation' ? ['batch_ref', 'allocation_state', 'work_scope'] : ['event_side'])].forEach(key => {
    if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key];
  });
  check(ref(value.selected_candidate_ref), '请选择需要查看的方案。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '准备与切换明细每页支持 20 或 50 条。');
  ['machine_ref', 'batch_ref'].forEach(key => check(value[key] === undefined || ref(value[key]), '准备与切换明细的批次或设备选择已失效，请重新选择。'));
  check(['asc', 'desc'].includes(value.order) && (section === 'preparation' ? preparationSorts : changeoverSorts).includes(value.sort), '准备与切换排序无效，请重新选择。');
  check(section === 'preparation' ? ['all', 'remaining'].includes(value.work_scope) && ['all', ...Object.keys(WorkbenchTerms.preparation_allocations)].includes(value.allocation_state)
    : ['all', 'selected', 'reference'].includes(value.event_side), '准备与切换筛选无效，请重新选择。');
  return value;
}
function _preparationDetails(payload, runRef, q, section = 'preparation') {
  const data = payload.data;
  check(data.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
    && data.scope.comparison_mode === q.comparison_mode && object(data.candidate) && data.candidate.candidate_ref === q.selected_candidate_ref
    && object(data.filters) && data.filters.section === section
    && object(data.page) && data.page.number === q.page && data.page.size === q.size,
  '准备与切换明细的方案、范围或页码已变化，请点“刷新准备与切换明细”。');
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref) check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '准备与切换明细的比较基准已变化，请点“刷新准备与切换明细”。');
  ['sort', 'order', ...(section === 'preparation' ? ['allocation_state', 'work_scope'] : ['event_side'])].forEach(key => check(data.filters[key] === q[key], '准备与切换明细的筛选或排序已变化，请点“刷新准备与切换明细”。'));
  ['machine_ref', ...(section === 'preparation' ? ['batch_ref'] : [])].forEach(key => check(data.filters[key] === (q[key] ?? null), '准备与切换明细的批次或设备已变化，请点“刷新准备与切换明细”。'));
  bindScope(payload, data, q);
  return data;
}
function validateReferenceWorkspace(payload, runRef, query) {
  const data = payload.data;
  check(object(data.candidate) && data.candidate.run_ref === runRef && data.candidate.candidate_ref === query.selected_candidate_ref
    && object(data.reference) && data.reference.kind === 'admission_official',
  '正式计划资料与本次比较不一致，请从方案对比重新打开。');
  check(ref(data.plan_ref) && data.plan_ref === data.reference.plan_ref && data.plan_ref === data.reference.baseline_ref
    && (!query.plan_ref || data.plan_ref === query.plan_ref), '比较基准的正式计划已变化，请从方案对比重新打开。');
  check(data.batch_ref === (query.batch_ref || null), '正式计划的批次范围已变化，请从方案对比重新打开。');
  for (const key of ['range_start', 'range_end']) if (query[key])
    check(data.time_scope && time(data.time_scope[key]) && timeKey(data.time_scope[key]) === timeKey(query[key]), '正式计划的时间范围已变化，请从方案对比重新打开。');
  if (query.resource_view) check(data.scope && data.scope.resource_view === query.resource_view, '正式计划的资源范围已变化，请从方案对比重新打开。');
  bindSnapshot(payload, query);
  return data;
}
function resourceFilters(query, section = 'resources') {
  const value = { resource_kind: 'machine', grain: 'day', pressure_threshold: 0.9, page: 1, size: 20 };
  const keys = ['resource_kind', 'resource_ref', 'grain', 'pressure_threshold', 'page', 'size'];
  if (section === 'resources') {
    Object.assign(value, { pressure_filter: 'all', sort: 'after_peak_utilization', order: 'desc', heatmap_page: 1, heatmap_size: 7 });
    keys.push('pressure_filter', 'sort', 'order', 'heatmap_page', 'heatmap_size', 'display_start', 'display_end');
  } else keys.push('bucket_start', 'bucket_end');
  keys.forEach(key => { if (query[key] !== undefined && query[key] !== null && query[key] !== '') value[key] = query[key]; });
  check(['machine', 'operator'].includes(value.resource_kind), '请选择设备或人员。');
  check(value.resource_ref === undefined || ref(value.resource_ref), '设备或人员选择已失效，请重新选择。');
  check(['hour', 'shift', 'day', 'week'].includes(value.grain) && typeof value.pressure_threshold === 'number'
    && Number.isFinite(value.pressure_threshold) && value.pressure_threshold > 0 && value.pressure_threshold <= 1,
  '请选择时间粒度与有效的高负荷关注线。');
  const rangeKeys = section === 'resources' ? ['display_start', 'display_end'] : ['bucket_start', 'bucket_end'];
  if (rangeKeys.some(key => value[key] !== undefined)) check(rangeKeys.every(key => time(value[key]))
    && timeKey(value[rangeKeys[0]]) < timeKey(value[rangeKeys[1]])
    && (section !== 'resources' || value.grain === 'hour'), '时段起止要同时填写，结束时间须晚于开始时间。');
  if (section === 'resources') check(['all', 'high_pressure', 'zero_capacity', 'conflicts', 'unknown', 'demand_overload'].includes(value.pressure_filter), '请选择资源负荷筛选。');
  if (section === 'resource-days') check(ref(value.resource_ref), '请选择要查看逐日明细的设备或人员。');
  check(Number.isInteger(value.page) && value.page > 0 && [20, 50].includes(value.size), '资源明细每页支持 20 或 50 条，请重新选择。');
  if (section === 'resources') check(Number.isInteger(value.heatmap_page) && value.heatmap_page > 0 && [7, 14, 31].includes(value.heatmap_size), '热力图每页支持 7、14 或 31 天，请重新选择。');
  if (query.snapshot_ref !== undefined && query.snapshot_ref !== null && query.snapshot_ref !== '') value.snapshot_ref = query.snapshot_ref;
  return value;
}
function resourceScope(runRef, query, section = 'resources') {
  const value = { ...scope(runRef, query), ...resourceFilters(query, section) };
  check(ref(value.selected_candidate_ref), '请选择查看方案及设备或人员。');
  return value;
}
function savedResourceView(query, cohort, comparison) {
  const next = { ...query }, refs = cohort[next.resource_kind || 'machine'];
  if (next.resource_ref && !refs.includes(next.resource_ref)) { delete next.resource_ref; delete next.snapshot_ref; next.page = 1; }
  if (comparison && next.display_start && (timeKey(next.display_start) < timeKey(comparison.range_start) || timeKey(next.display_end) > timeKey(comparison.range_end))) {
    delete next.display_start; delete next.display_end; delete next.snapshot_ref; next.heatmap_page = 1;
  }
  return next;
}
// 资源首屏的 data 在方案对比首屏之外多带 resource_result（内嵌的资源读取结果）与 resource_query（实际采用的资源筛选）。
function _validateResourceWorkspace(payload, runRef, q, filters) {
  const data = _validateDecisionSummary(payload, runRef, q), { resource_result: resources, resource_query: effective } = data, cohort = data.scope.resource_refs;
  check(object(cohort),
    '参与比较的设备或人员资料不完整，请刷新方案对比。');
  const expected = savedResourceView(filters, cohort, data.scope);
  check(object(effective) && equal(effective, expected),
    '恢复的资源筛选与当前范围不一致，请刷新方案对比。');
  const candidate = data.candidates.find(row => row.candidate_ref === data.scope.selected_candidate_ref);
  if (!candidate) {
    check(resources === null, '当前方案没有可查看的资源结果，请刷新方案对比。'); return data;
  }
  check(object(resources), '资源读取结果未记录，请刷新方案对比。');
  // 内嵌的资源结果没有经过传输层：成功时按同一份查询信封核对；失败时原样留给资源页签，由 APSWorkbenchTransport.failure 统一解析。
  if (resources.ok === true) {
    T.envelope(resources);
    const comparison = { comparison_mode: data.scope.comparison_mode, resource_view: data.scope.resource_view,
      selected_candidate_ref: data.scope.selected_candidate_ref, range_start: data.scope.range_start, range_end: data.scope.range_end,
      ...(data.scope.comparison_mode === 'candidates' ? { reference_candidate_ref: data.scope.reference.candidate_ref } : {}) };
    _resourceDetails(resources, runRef, { ...comparison, ...expected }, 'resources', cohort);
  }
  return data;
}
function _resourceDetails(payload, runRef, q, section = 'resources', expectedRefs) {
  const data = payload.data;
  check(data.run_ref === runRef && object(data.scope) && data.scope.run_ref === runRef && data.scope.selected_candidate_ref === q.selected_candidate_ref
    && data.scope.comparison_mode === q.comparison_mode && object(data.candidate) && data.candidate.candidate_ref === q.selected_candidate_ref
    && object(data.filters) && data.filters.section === section && data.filters.resource_kind === q.resource_kind
    && data.filters.resource_ref === (q.resource_ref ?? null) && object(data.page) && data.page.number === q.page && data.page.size === q.size,
  '资源明细的方案、设备人员范围或页码已变化，请点“刷新资源影响”。');
  if (q.comparison_mode === 'candidates' && q.reference_candidate_ref)
    check(data.scope.reference && data.scope.reference.candidate_ref === q.reference_candidate_ref, '资源明细的比较基准已变化，请点“刷新资源影响”。');
  bindScope(payload, data, q);
  check(data.filters.grain === q.grain && data.filters.pressure_threshold === q.pressure_threshold
    && (section === 'resources' || ['bucket_start', 'bucket_end'].every(key => data.filters[key] === (q[key] ?? null))),
  '资源时间粒度、关注线或所选时段已变化，请点“刷新资源影响”。');
  const cohort = data.scope.resource_refs;
  check(object(cohort), '参与比较的设备或人员资料不完整，请点“刷新资源影响”。');
  if (expectedRefs) check(['machine', 'operator'].every(kind => JSON.stringify(cohort[kind]) === JSON.stringify(expectedRefs[kind])), '参与比较的设备或人员已变化，请点“刷新资源影响”。');
  if (section === 'resources') {
    ['pressure_filter', 'sort', 'order'].forEach(key => check(data.filters[key] === q[key], '资源明细的筛选或排序已变化，请点“刷新资源影响”。'));
    check(object(data.heatmap) && data.heatmap.grain === q.grain && object(data.heatmap.page)
      && data.heatmap.page.number === q.heatmap_page && data.heatmap.page.size === q.heatmap_size,
    '资源表或热力图的设备人员范围已变化，请点“刷新资源影响”。');
  } else {
    check(object(data.resource) && data.resource.ref === q.resource_ref && data.resource.kind === q.resource_kind
      && cohort[q.resource_kind].includes(q.resource_ref), '逐日明细的设备或人员已变化，请点“刷新资源影响”。');
  }
  return data;
}
const BASE = '/api/workbench/v1/scheduling/runs/';
const read = (runRef, leaf, query, signal) => T.read(BASE + runRef + '/decision' + leaf, query, { signal, timeout: 60000 });
const RunDecisionAPI = {
  async decision(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '', q, signal); _decisionCore(value, runRef, q); return value; },
  async decisionSummary(runRef, query, signal) { const q = scope(runRef, query), value = await read(runRef, '/summary', q, signal); _validateDecisionSummary(value, runRef, q); return value; },
  async resourceWorkspace(runRef, query, savedQuery, signal) {
    const q = scope(runRef, query), filters = resourceFilters(savedQuery), wire = { ...filters }, resourceSnapshot = wire.snapshot_ref;
    delete wire.snapshot_ref;
    const value = await read(runRef, '/resource-workspace', { ...q, ...wire, ...(resourceSnapshot !== undefined ? { resource_snapshot_ref: resourceSnapshot } : {}) }, signal);
    _validateResourceWorkspace(value, runRef, q, filters); return value;
  },
  async decisionDetails(runRef, query, section, signal) { const q = detailScope(runRef, query, section), value = await read(runRef, '/' + section, q, signal); _details(value, runRef, q, section); return value; },
  async completionBatches(runRef, query, signal) {
    const q = completionScope(runRef, query), value = await read(runRef, '/completion-batches', q, signal); _validateCompletionBatches(value, runRef, q); return value;
  },
  async process(runRef, query, signal) { const q = processScope(runRef, query), value = await read(runRef, '/process', q, signal); _processDetails(value, runRef, q); return value; },
  async referenceWorkspace(runRef, query, signal) {
    const q = { ...scope(runRef, { ...query, comparison_mode: 'admission_official' }) };
    if (query.batch_ref) q.batch_ref = query.batch_ref;
    const value = await read(runRef, '/reference-workspace', q, signal); validateReferenceWorkspace(value, runRef, { ...q, plan_ref: query.plan_ref }); return value;
  },
  async resources(runRef, query, signal) {
    const q = resourceScope(runRef, query), value = await read(runRef, '/resources', q, signal);
    _resourceDetails(value, runRef, q, 'resources', query.expected_resource_refs); return value;
  },
  async resourceDays(runRef, query, signal) {
    const q = resourceScope(runRef, query, 'resource-days'), value = await read(runRef, '/resource-days', q, signal);
    _resourceDetails(value, runRef, q, 'resource-days', query.expected_resource_refs); return value;
  },
  async preparation(runRef, query, signal) { const q = preparationScope(runRef, query), value = await read(runRef, '/preparation', q, signal); _preparationDetails(value, runRef, q); return value; },
  async changeovers(runRef, query, signal) { const q = preparationScope(runRef, query, 'changeovers'), value = await read(runRef, '/changeovers', q, signal); _preparationDetails(value, runRef, q, 'changeovers'); return value; },
  async decisionExport(runRef, query, snapshotRef, format, signal, section) {
    check(['csv', 'xlsx'].includes(format) && typeof snapshotRef === 'string' && snapshotRef.length > 0);
    const detailSection = query.filter_section || (['batches', 'operations', 'resources', 'resource-days', 'preparation', 'changeovers', 'process'].includes(section) ? section : null);
    const q = detailSection === 'process' ? processScope(runRef, query) : ['preparation', 'changeovers'].includes(detailSection) ? preparationScope(runRef, query, detailSection)
      : ['resources', 'resource-days'].includes(detailSection) ? resourceScope(runRef, query, detailSection) : detailSection ? detailScope(runRef, query, detailSection) : scope(runRef, query);
    for (const key of ['page', 'size', 'heatmap_page', 'heatmap_size']) delete q[key];
    const file = await T.download(BASE + runRef + '/decision/export', { ...q, ...(detailSection ? { filter_section: detailSection } : {}), snapshot_ref: snapshotRef, format, section },
      { signal, timeout: 60000, types: [T.types[format]] });
    check(file.header('X-Workbench-Run-Ref') === runRef && file.header('X-Workbench-Snapshot-Ref') === snapshotRef, '比较资料已更新，请关闭导出窗口，刷新后重新导出。');
    // 传输层已校验附件、文件名与后缀、格式、魔数与非空；这里只断言本领域业务头。
    const rowCount = file.header('X-Workbench-Row-Count');
    check(rowCount !== null && /^\d+$/.test(rowCount), '导出文件没有读取到内容，请重新点击下载。');
    return { blob: file.blob, row_count: Number(rowCount), filename: file.filename };
  },
  resourceFilters, savedResourceView, scope, detailScope,
  completionScope, processScope, resourceScope, preparationScope
};
export { RunDecisionAPI, resourceFilters, savedResourceView, scope, detailScope,
  completionScope, processScope, resourceScope, preparationScope };
export default RunDecisionAPI;
